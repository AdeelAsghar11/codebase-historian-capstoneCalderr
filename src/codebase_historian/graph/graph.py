"""
NetworkX-backed Codebase Knowledge Graph representation and query interface.
"""

import json
from pathlib import Path
from typing import Any

import networkx as nx

from codebase_historian.graph.models import EdgeType, NodeType


def file_node_id(path: str) -> str:
    clean_path = path.replace("\\", "/")
    return f"file:{clean_path}"


def commit_node_id(sha: str) -> str:
    return f"commit:{sha}"


def author_node_id(author_id: str) -> str:
    return f"author:{author_id}"


def pr_node_id(number: int) -> str:
    return f"pr:{number}"


def issue_node_id(number: int) -> str:
    return f"issue:{number}"


class CodebaseKnowledgeGraph:
    """Directed multigraph representing files, commits, authors, and relationships."""

    def __init__(self, graph: nx.MultiDiGraph | None = None):
        self.g: nx.MultiDiGraph = graph if graph is not None else nx.MultiDiGraph()

    # --- Node Queries ---

    def get_file_history(self, file_path: str) -> list[dict[str, Any]]:
        """
        Get all commits that modified a file, with commit details and diff stats.
        Returns list ordered chronologically by commit timestamp.
        """
        f_id = file_node_id(file_path)
        if not self.g.has_node(f_id):
            return []

        history = []
        # In-edges to File with type MODIFIES originate from Commit nodes
        for u, v, k, data in self.g.in_edges(f_id, keys=True, data=True):
            if data.get("type") == EdgeType.MODIFIES.value:
                commit_data = self.g.nodes.get(u, {})
                history.append(
                    {
                        "commit_sha": commit_data.get("sha", u.replace("commit:", "")),
                        "message": commit_data.get("message", ""),
                        "timestamp": commit_data.get("timestamp", ""),
                        "author": commit_data.get("author_id", ""),
                        "author_name": commit_data.get("author_name", ""),
                        "lines_added": data.get("lines_added", 0),
                        "lines_removed": data.get("lines_removed", 0),
                        "diff_summary": data.get("diff_summary", ""),
                    }
                )

        history.sort(key=lambda x: x["timestamp"])
        return history

    def get_file_co_changes(
        self, file_path: str, min_count: int = 1
    ) -> list[dict[str, Any]]:
        """Get files that historically co-change with the given file."""
        f_id = file_node_id(file_path)
        if not self.g.has_node(f_id):
            return []

        co_changes = []
        for u, v, k, data in self.g.edges(f_id, keys=True, data=True):
            if data.get("type") == EdgeType.CO_CHANGES_WITH.value:
                other_file = v.replace("file:", "")
                count = data.get("co_change_count", 1)
                if count >= min_count:
                    co_changes.append(
                        {
                            "file": other_file,
                            "co_change_count": count,
                            "last_commit": data.get("last_co_change_commit", ""),
                        }
                    )

        co_changes.sort(key=lambda x: x["co_change_count"], reverse=True)
        return co_changes

    def get_file_dependencies(self, file_path: str) -> dict[str, list[str]]:
        """Get static dependencies for a file (both upstream imported and downstream consumers)."""
        f_id = file_node_id(file_path)
        if not self.g.has_node(f_id):
            return {"imports": [], "imported_by": []}

        # Outgoing DEPENDS_ON edges -> files this file imports
        imports = []
        for _, target, data in self.g.out_edges(f_id, data=True):
            if data.get("type") == EdgeType.DEPENDS_ON.value:
                imports.append(target.replace("file:", ""))

        # Incoming DEPENDS_ON edges -> files that import this file
        imported_by = []
        for source, _, data in self.g.in_edges(f_id, data=True):
            if data.get("type") == EdgeType.DEPENDS_ON.value:
                imported_by.append(source.replace("file:", ""))

        return {
            "imports": sorted(list(set(imports))),
            "imported_by": sorted(list(set(imported_by))),
        }

    def get_blast_radius(
        self,
        file_paths: list[str],
        min_co_changes: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Predict blast radius for a proposed change to one or more files.
        Combines historical co-change patterns and AST dependency links.
        Returns sorted list of affected files with evidence category and confidence.
        """
        targets = {p.replace("\\", "/") for p in file_paths}
        affected: dict[str, dict[str, Any]] = {}

        for file_path in targets:
            # 1. Co-change evidence
            co_changes = self.get_file_co_changes(file_path, min_count=min_co_changes)
            for cc in co_changes:
                other = cc["file"]
                if other in targets:
                    continue
                if other not in affected:
                    affected[other] = {
                        "file": other,
                        "co_change_count": cc["co_change_count"],
                        "has_dependency": False,
                        "dependency_kind": None,
                    }
                else:
                    affected[other]["co_change_count"] = max(
                        affected[other].get("co_change_count", 0), cc["co_change_count"]
                    )

            # 2. Dependency evidence
            deps = self.get_file_dependencies(file_path)
            # Files that import this file are directly impacted by changes
            for consumer in deps["imported_by"]:
                if consumer in targets:
                    continue
                if consumer not in affected:
                    affected[consumer] = {
                        "file": consumer,
                        "co_change_count": 0,
                        "has_dependency": True,
                        "dependency_kind": "consumer",
                    }
                else:
                    affected[consumer]["has_dependency"] = True
                    affected[consumer]["dependency_kind"] = "consumer"

            # Files this file imports may also need review
            for upstream in deps["imports"]:
                if upstream in targets:
                    continue
                if upstream not in affected:
                    affected[upstream] = {
                        "file": upstream,
                        "co_change_count": 0,
                        "has_dependency": True,
                        "dependency_kind": "upstream",
                    }
                else:
                    affected[upstream]["has_dependency"] = True

        results = []
        for file, data in affected.items():
            has_co = data["co_change_count"] > 0
            has_dep = data["has_dependency"]

            if has_co and has_dep:
                evidence = "both"
                # High confidence when both co-change and AST dependency align
                confidence = min(0.95, 0.7 + (0.05 * data["co_change_count"]))
            elif has_dep:
                evidence = "dependency"
                confidence = 0.75
            else:
                evidence = "co-change"
                confidence = min(0.85, 0.5 + (0.1 * data["co_change_count"]))

            results.append(
                {
                    "file": file,
                    "evidence": evidence,
                    "confidence": round(confidence, 2),
                    "co_change_count": data["co_change_count"],
                    "dependency_kind": data["dependency_kind"],
                }
            )

        results.sort(key=lambda x: (x["confidence"], x["co_change_count"]), reverse=True)
        return results

    def compute_centralities(self) -> dict[str, float]:
        """
        Compute graph centrality across file nodes using PageRank on the file-relation subgraph.
        Annotates 'centrality' property on File nodes and returns mapping {file_path: score}.
        """
        # Build simple directed graph between files (from DEPENDS_ON and CO_CHANGES_WITH)
        file_subgraph = nx.DiGraph()
        file_nodes = [
            n for n, d in self.g.nodes(data=True) if d.get("type") == NodeType.FILE.value
        ]

        if not file_nodes:
            return {}

        file_subgraph.add_nodes_from(file_nodes)

        for u, v, data in self.g.edges(data=True):
            if u in file_nodes and v in file_nodes:
                edge_type = data.get("type")
                if edge_type == EdgeType.DEPENDS_ON.value:
                    weight = file_subgraph.get_edge_data(u, v, {}).get("weight", 0) + 2.0
                    file_subgraph.add_edge(u, v, weight=weight)
                elif edge_type == EdgeType.CO_CHANGES_WITH.value:
                    count = data.get("co_change_count", 1)
                    weight = file_subgraph.get_edge_data(u, v, {}).get("weight", 0) + (1.0 * count)
                    file_subgraph.add_edge(u, v, weight=weight)

        try:
            ranks = nx.pagerank(file_subgraph, weight="weight")
        except Exception:
            # Fallback to degree centrality if pagerank does not converge
            ranks = nx.degree_centrality(file_subgraph)

        centrality_map = {}
        for node_id, score in ranks.items():
            path = node_id.replace("file:", "")
            centrality_map[path] = round(score, 4)
            self.g.nodes[node_id]["centrality"] = round(score, 4)

        return centrality_map

    def get_central_files(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Get the most central files in the repository."""
        file_nodes = [
            (n.replace("file:", ""), d.get("centrality", 0.0))
            for n, d in self.g.nodes(data=True)
            if d.get("type") == NodeType.FILE.value
        ]
        file_nodes.sort(key=lambda x: x[1], reverse=True)
        return [{"file": path, "centrality": score} for path, score in file_nodes[:top_n]]

    def summary(self) -> dict[str, Any]:
        """Return graph counts and metadata."""
        node_counts: dict[str, int] = {}
        for _, data in self.g.nodes(data=True):
            t = data.get("type", "Unknown")
            node_counts[t] = node_counts.get(t, 0) + 1

        edge_counts: dict[str, int] = {}
        for _, _, data in self.g.edges(data=True):
            t = data.get("type", "Unknown")
            edge_counts[t] = edge_counts.get(t, 0) + 1

        return {
            "total_nodes": self.g.number_of_nodes(),
            "total_edges": self.g.number_of_edges(),
            "nodes_by_type": node_counts,
            "edges_by_type": edge_counts,
        }

    def save(self, file_path: str | Path) -> None:
        """Serialize graph to JSON file."""
        data = nx.node_link_data(self.g, edges="edges")
        Path(file_path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, file_path: str | Path) -> "CodebaseKnowledgeGraph":
        """Deserialize graph from JSON file."""
        content = Path(file_path).read_text(encoding="utf-8")
        data = json.loads(content)
        graph = nx.node_link_graph(data, directed=True, multigraph=True, edges="edges")
        return cls(graph)
