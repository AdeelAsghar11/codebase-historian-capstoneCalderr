"""
Historian agent.
Explains why a file, function, or pattern exists, citing commits, PRs, and discussions.
"""

from typing import Any

from codebase_historian.agents.schemas import Citation, ExplainResponse
from codebase_historian.agents.state import AgentState
from codebase_historian.graph.graph import CodebaseKnowledgeGraph
from codebase_historian.memory.store import SQLiteMemoryStore
from codebase_historian.retrieval.hybrid_index import HybridRetrievalIndex


class HistorianAgent:
    """Explains codebase rationale backed by git history, knowledge graph, and retrieval."""

    def __init__(
        self,
        knowledge_graph: CodebaseKnowledgeGraph | None = None,
        retrieval_index: HybridRetrievalIndex | None = None,
        memory_store: SQLiteMemoryStore | None = None,
        llm: Any | None = None,
    ):
        self.kg = knowledge_graph
        self.index = retrieval_index
        self.memory = memory_store
        self.llm = llm

    def explain(self, target: str, query: str = "") -> ExplainResponse:
        """Generate evidence-grounded explanation with verifiable citations."""
        clean_target = target.replace("\\", "/").strip()
        citations: list[Citation] = []

        # 1. Check reconciled memory for existing active explanation
        if self.memory:
            cached_entries = self.memory.get_by_subject(clean_target)
            active_entries = [e for e in cached_entries if e.status.value == "active"]
            if active_entries:
                top_entry = active_entries[0]
                citations.append(
                    Citation(
                        commit_sha=top_entry.source_commit_sha,
                        excerpt=f"Reconciled memory entry (validated {top_entry.last_validated_at.date()})",
                    )
                )
                return ExplainResponse(
                    answer=top_entry.claim_text,
                    citations=citations,
                    confidence=0.92,
                )

        # 2. Query Knowledge Graph for file commit history
        history: list[dict[str, Any]] = []
        if self.kg:
            history = self.kg.get_file_history(clean_target)

        # 3. Query Hybrid Index for relevant PRs and discussions
        search_results = []
        if self.index:
            search_query = query if query else f"{clean_target} rationale design"
            search_results = self.index.search(search_query, top_k=3, subject_filter=clean_target)
            if not search_results:
                search_results = self.index.search(search_query, top_k=3)

        # 4. Synthesize explanation and citations
        if not history and not search_results:
            return ExplainResponse(
                answer=f"No historical commits or documentation found for target '{clean_target}'.",
                citations=[],
                confidence=0.1,
            )

        answer_parts = [f"### Historical Context for `{clean_target}`\n"]

        if history:
            initial_commit = history[0]
            answer_parts.append(
                f"- **Origination**: Introduced in commit `{initial_commit['commit_sha'][:8]}` by **{initial_commit['author_name']}** with message: \"{initial_commit['message']}\"."
            )
            citations.append(
                Citation(
                    commit_sha=initial_commit["commit_sha"],
                    excerpt=f"Created file: {initial_commit['message']}",
                )
            )

            if len(history) > 1:
                latest_commit = history[-1]
                answer_parts.append(
                    f"- **Latest Evolution**: Last modified in commit `{latest_commit['commit_sha'][:8]}`: \"{latest_commit['message']}\" (+{latest_commit['lines_added']}/-{latest_commit['lines_removed']} lines)."
                )
                citations.append(
                    Citation(
                        commit_sha=latest_commit["commit_sha"],
                        excerpt=f"Modified file: {latest_commit['message']}",
                    )
                )

        for sr in search_results:
            if sr.doc_type.value == "pull_request":
                citations.append(
                    Citation(
                        pr_number=sr.metadata.get("number"),
                        excerpt=sr.text[:120] + "...",
                    )
                )
            elif sr.doc_type.value == "docstring":
                answer_parts.append(f"- **Documented Design**: {sr.text.splitlines()[-1] if sr.text else ''}")

        answer = "\n".join(answer_parts)

        # Record into memory store if available
        if self.memory and history:
            self.memory.add_entry(
                subject=clean_target,
                claim_text=answer,
                source_commit_sha=history[-1]["commit_sha"],
            )

        return ExplainResponse(
            answer=answer,
            citations=citations,
            confidence=0.88,
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node execution for Historian."""
        target = state.get("target") or "repository"
        query = state.get("query", "")
        response = self.explain(target, query)
        return {
            "explain_response": response,
            "status": "historian_completed",
        }
