"""
Knowledge graph builder.
Populates NetworkX MultiDiGraph from ingestion pipeline results and PR/issue data.
"""


from codebase_historian.graph.graph import (
    CodebaseKnowledgeGraph,
    author_node_id,
    commit_node_id,
    file_node_id,
    issue_node_id,
    pr_node_id,
)
from codebase_historian.graph.models import (
    EdgeType,
    IssueNodeData,
    NodeType,
    PullRequestNodeData,
)
from codebase_historian.ingestion.models import (
    CoChangeRecord,
    CommitRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.pipeline import IngestionResult


class KnowledgeGraphBuilder:
    """Constructs and populates a CodebaseKnowledgeGraph."""

    def __init__(self, existing_graph: CodebaseKnowledgeGraph | None = None):
        self.kg = existing_graph or CodebaseKnowledgeGraph()

    def build_from_ingestion(self, result: IngestionResult) -> CodebaseKnowledgeGraph:
        """Populate the graph from an IngestionResult and compute centralities."""
        # 1. Add Commits, Authors, and MODIFIES edges
        self.add_commits(result.commits)

        # 2. Add Co-change edges
        self.add_co_changes(result.co_changes)

        # 3. Add AST File nodes and DEPENDS_ON edges
        self.add_file_structures(result.file_structures)
        self.add_dependencies(result.dependencies)

        # 4. Compute file centrality scores
        self.kg.compute_centralities()

        return self.kg

    def add_commits(self, commits: list[CommitRecord]) -> None:
        """Add commits, authors, and file modification edges."""
        for commit in commits:
            c_id = commit_node_id(commit.sha)
            a_id = author_node_id(commit.author.id)

            # Ensure Author node exists
            if not self.kg.g.has_node(a_id):
                self.kg.g.add_node(
                    a_id,
                    type=NodeType.AUTHOR.value,
                    id=commit.author.id,
                    display_name=commit.author.display_name,
                )

            # Add Commit node
            ts_str = commit.timestamp.isoformat()
            self.kg.g.add_node(
                c_id,
                type=NodeType.COMMIT.value,
                sha=commit.sha,
                author_id=commit.author.id,
                author_name=commit.author.display_name,
                timestamp=ts_str,
                message=commit.message,
                parent_shas=commit.parent_shas,
            )

            # Add AUTHORED_BY edge
            if not any(
                d.get("type") == EdgeType.AUTHORED_BY.value
                for _, _, d in self.kg.g.edges(c_id, data=True)
            ):
                self.kg.g.add_edge(
                    c_id,
                    a_id,
                    type=EdgeType.AUTHORED_BY.value,
                )

            # Process file modifications
            for mod in commit.modifications:
                f_id = file_node_id(mod.path)

                if not self.kg.g.has_node(f_id):
                    self.kg.g.add_node(
                        f_id,
                        type=NodeType.FILE.value,
                        path=mod.path,
                        language="python" if mod.path.endswith(".py") else "unknown",
                        first_seen_commit=commit.sha,
                        last_modified_commit=commit.sha,
                        centrality=0.0,
                    )
                else:
                    # Update last modified commit
                    self.kg.g.nodes[f_id]["last_modified_commit"] = commit.sha

                # Add MODIFIES edge (Commit -> File) if not already added
                if not any(
                    v == f_id and d.get("type") == EdgeType.MODIFIES.value
                    for _, v, d in self.kg.g.edges(c_id, data=True)
                ):
                    self.kg.g.add_edge(
                        c_id,
                        f_id,
                        type=EdgeType.MODIFIES.value,
                        change_type=mod.change_type,
                        lines_added=mod.lines_added,
                        lines_removed=mod.lines_removed,
                        diff_summary=mod.diff_summary or "",
                    )

    def add_co_changes(self, co_changes: list[CoChangeRecord]) -> None:
        """Add bidirectional CO_CHANGES_WITH edges between files."""
        for cc in co_changes:
            f1_id = file_node_id(cc.file_a)
            f2_id = file_node_id(cc.file_b)

            # Ensure both file nodes exist
            for f_id, path in [(f1_id, cc.file_a), (f2_id, cc.file_b)]:
                if not self.kg.g.has_node(f_id):
                    self.kg.g.add_node(
                        f_id,
                        type=NodeType.FILE.value,
                        path=path,
                        language="python" if path.endswith(".py") else "unknown",
                        first_seen_commit=None,
                        last_modified_commit=None,
                        centrality=0.0,
                    )

            # Add or update bidirectional edges without duplicate multi-edges
            edge_attrs = {
                "type": EdgeType.CO_CHANGES_WITH.value,
                "co_change_count": cc.co_change_count,
                "last_co_change_commit": cc.last_co_change_commit,
            }

            existing_f1_f2 = False
            if self.kg.g.has_edge(f1_id, f2_id):
                for _, d in self.kg.g.get_edge_data(f1_id, f2_id).items():
                    if d.get("type") == EdgeType.CO_CHANGES_WITH.value:
                        d["co_change_count"] = max(d.get("co_change_count", 0), cc.co_change_count)
                        d["last_co_change_commit"] = cc.last_co_change_commit
                        existing_f1_f2 = True
                        break
            if not existing_f1_f2:
                self.kg.g.add_edge(f1_id, f2_id, **edge_attrs)

            existing_f2_f1 = False
            if self.kg.g.has_edge(f2_id, f1_id):
                for _, d in self.kg.g.get_edge_data(f2_id, f1_id).items():
                    if d.get("type") == EdgeType.CO_CHANGES_WITH.value:
                        d["co_change_count"] = max(d.get("co_change_count", 0), cc.co_change_count)
                        d["last_co_change_commit"] = cc.last_co_change_commit
                        existing_f2_f1 = True
                        break
            if not existing_f2_f1:
                self.kg.g.add_edge(f2_id, f1_id, **edge_attrs)

    def add_file_structures(self, structures: list[FileStructureRecord]) -> None:
        """Ensure File nodes exist for all parsed source files and attach metadata."""
        for s in structures:
            f_id = file_node_id(s.path)
            if not self.kg.g.has_node(f_id):
                self.kg.g.add_node(
                    f_id,
                    type=NodeType.FILE.value,
                    path=s.path,
                    language=s.language,
                    first_seen_commit=None,
                    last_modified_commit=None,
                    centrality=0.0,
                )
            # Store symbol metadata if present
            self.kg.g.nodes[f_id]["has_ast"] = True
            self.kg.g.nodes[f_id]["classes_count"] = len(s.classes)
            self.kg.g.nodes[f_id]["functions_count"] = len(s.functions)
            if s.docstring:
                self.kg.g.nodes[f_id]["docstring"] = s.docstring

    def add_dependencies(self, dependencies: list[tuple[str, str, str]]) -> None:
        """Add DEPENDS_ON edges from AST analysis: source_file -> target_file."""
        for source, target, kind in dependencies:
            s_id = file_node_id(source)
            t_id = file_node_id(target)

            for f_id, path in [(s_id, source), (t_id, target)]:
                if not self.kg.g.has_node(f_id):
                    self.kg.g.add_node(
                        f_id,
                        type=NodeType.FILE.value,
                        path=path,
                        language="python" if path.endswith(".py") else "unknown",
                        centrality=0.0,
                    )

            if not any(
                v == t_id and d.get("type") == EdgeType.DEPENDS_ON.value
                for _, v, d in self.kg.g.edges(s_id, data=True)
            ):
                self.kg.g.add_edge(
                    s_id,
                    t_id,
                    type=EdgeType.DEPENDS_ON.value,
                    import_kind=kind,
                )

    def add_pull_request(
        self,
        pr_data: PullRequestNodeData,
        commit_shas: list[str] = None,
        referenced_issue_numbers: list[int] = None,
    ) -> None:
        """Add PullRequest node and its INCLUDES and REFERENCES edges."""
        p_id = pr_node_id(pr_data.number)
        self.kg.g.add_node(
            p_id,
            type=NodeType.PULL_REQUEST.value,
            number=pr_data.number,
            title=pr_data.title,
            description=pr_data.description or "",
            author=pr_data.author,
            merged_at=pr_data.merged_at or "",
            status=pr_data.status,
        )

        if commit_shas:
            for sha in commit_shas:
                c_id = commit_node_id(sha)
                if self.kg.g.has_node(c_id):
                    self.kg.g.add_edge(p_id, c_id, type=EdgeType.INCLUDES.value)

        if referenced_issue_numbers:
            for iss_num in referenced_issue_numbers:
                iss_id = issue_node_id(iss_num)
                if self.kg.g.has_node(iss_id):
                    self.kg.g.add_edge(p_id, iss_id, type=EdgeType.REFERENCES.value)

    def add_issue(self, issue_data: IssueNodeData) -> None:
        """Add Issue node to the knowledge graph."""
        i_id = issue_node_id(issue_data.number)
        self.kg.g.add_node(
            i_id,
            type=NodeType.ISSUE.value,
            number=issue_data.number,
            title=issue_data.title,
            body=issue_data.body or "",
            author=issue_data.author,
            closed_at=issue_data.closed_at or "",
            status=issue_data.status,
        )
