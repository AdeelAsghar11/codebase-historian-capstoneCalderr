"""
Historian agent.
Explains why a file, function, or pattern exists, citing commits, PRs, and discussions.
"""

import ast
import os
import unicodedata
from pathlib import Path
from typing import Any

from codebase_historian.agents.schemas import Citation, ExplainResponse
from codebase_historian.agents.state import AgentState
from codebase_historian.config import settings
from codebase_historian.graph.graph import CodebaseKnowledgeGraph, file_node_id
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

        # Auto-initialize LLM if Groq API key is configured and no LLM was explicitly passed
        if llm is None:
            groq_key = os.environ.get("GROQ_API_KEY") or settings.groq_api_key
            if groq_key and groq_key.strip():
                try:
                    from langchain_groq import ChatGroq

                    llm = ChatGroq(model_name=settings.llm_model, api_key=groq_key.strip())
                except Exception:
                    pass
        self.llm = llm

    def explain(self, target: str, query: str = "") -> ExplainResponse:
        """Generate evidence-grounded explanation with verifiable citations and plain-English narrative."""
        clean_target = target.replace("\\", "/").strip()
        citations: list[Citation] = []

        # 1. Check reconciled memory for existing active explanation
        if self.memory:
            cached_entries = self.memory.get_by_subject(clean_target)
            active_entries = [
                e for e in cached_entries
                if e.status.value == "active" and ("Overview" in e.claim_text or "What it does" in e.claim_text)
            ]
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

        # 2. Query Knowledge Graph for file metadata, AST structure, and commit history
        history: list[dict[str, Any]] = []
        node_data: dict[str, Any] = {}
        deps: dict[str, list[str]] = {"upstream": [], "downstream": []}
        co_changes: list[dict[str, Any]] = []

        if self.kg:
            history = self.kg.get_file_history(clean_target)
            f_id = file_node_id(clean_target)
            node_data = self.kg.g.nodes.get(f_id, {})
            deps = self.kg.get_file_dependencies(clean_target)
            co_changes = self.kg.get_file_co_changes(clean_target, min_count=2)

        # Extract docstring and AST details (from graph or local file)
        docstring = node_data.get("docstring", "")
        classes_count = node_data.get("classes_count", 0)
        functions_count = node_data.get("functions_count", 0)

        local_file = Path(clean_target)
        if not docstring and local_file.exists() and local_file.suffix == ".py":
            try:
                tree = ast.parse(local_file.read_text(encoding="utf-8", errors="ignore"))
                docstring = ast.get_docstring(tree) or ""
                if classes_count == 0:
                    classes_count = len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)])
                if functions_count == 0:
                    functions_count = len([n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))])
            except Exception:
                pass

        # 3. Query Hybrid Index for relevant PRs and discussions
        search_results = []
        if self.index:
            search_query = query if query else f"{clean_target} rationale design"
            search_results = self.index.search(search_query, top_k=3, subject_filter=clean_target)
            if not search_results:
                search_results = self.index.search(search_query, top_k=3)

        # 4. Handle empty target
        if not history and not search_results and not docstring:
            return ExplainResponse(
                answer=f"No historical commits or documentation found for target '{clean_target}'.",
                citations=[],
                confidence=0.1,
            )

        # 5. Build citations
        initial_commit = history[0] if history else None
        latest_commit = history[-1] if history else None

        if initial_commit:
            citations.append(
                Citation(
                    commit_sha=initial_commit["commit_sha"],
                    excerpt=f"Created file: {initial_commit['message']}",
                )
            )

        if latest_commit and latest_commit != initial_commit:
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

        # 6. Synthesize Plain-English Explanation (LLM or deterministic AST synthesis)
        answer = self._synthesize_explanation(
            clean_target=clean_target,
            docstring=docstring,
            classes_count=classes_count,
            functions_count=functions_count,
            deps=deps,
            co_changes=co_changes,
            history=history,
            initial_commit=initial_commit,
            latest_commit=latest_commit,
            search_results=search_results,
        )

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

    def _synthesize_explanation(
        self,
        clean_target: str,
        docstring: str,
        classes_count: int,
        functions_count: int,
        deps: dict[str, list[str]],
        co_changes: list[dict[str, Any]],
        history: list[dict[str, Any]],
        initial_commit: dict[str, Any] | None,
        latest_commit: dict[str, Any] | None,
        search_results: list[Any],
    ) -> str:
        """Synthesize rich, plain-English explanation of purpose, architecture, and history."""
        # Try LLM synthesis if available
        if self.llm:
            try:
                prompt = (
                    f"You are an expert software historian explaining a codebase module to a developer.\n"
                    f"Target file: {clean_target}\n"
                    f"Docstring: {docstring or 'None'}\n"
                    f"Classes: {classes_count}, Functions: {functions_count}\n"
                    f"Upstream dependencies: {deps.get('upstream', [])[:5]}\n"
                    f"Downstream consumers: {deps.get('downstream', [])[:5]}\n"
                    f"Initial commit: {initial_commit}\n"
                    f"Latest commit: {latest_commit}\n\n"
                    f"Write a clear, articulate, plain-English explanation covering:\n"
                    f"1. Overview & Purpose: What this code does in plain English.\n"
                    f"2. Architectural Role: How it connects to the rest of the application.\n"
                    f"3. Historical Rationale & Evolution: Why it was created and how it changed over time.\n"
                    f"Retain the exact commit SHAs and historical details."
                )
                response = self.llm.invoke(prompt)
                llm_text = getattr(response, "content", str(response)).strip()
                if len(llm_text) > 80:
                    # Sanitize special Unicode characters for Windows cp1252 consoles
                    replacements = {
                        "\u2011": "-",
                        "\u2012": "-",
                        "\u2013": "-",
                        "\u2014": "--",
                        "\u2018": "'",
                        "\u2019": "'",
                        "\u201c": '"',
                        "\u201d": '"',
                        "\u2026": "...",
                        "\u2022": "*",
                        "\u202f": " ",
                        "\u00a0": " ",
                        "\u200b": "",
                    }
                    for old, new in replacements.items():
                        llm_text = llm_text.replace(old, new)
                    llm_text = unicodedata.normalize("NFKD", llm_text).encode("ascii", "ignore").decode("ascii")
                    return llm_text
            except Exception:
                pass

        # Deterministic rich plain-English synthesis
        sections = [f"### Plain-English Overview: `{clean_target}`\n"]

        # Plain-English purpose summary
        if docstring:
            first_para = docstring.strip().split("\n\n")[0].replace("\n", " ")
            sections.append(f"**What it does**:\n`{clean_target}` {first_para[0].lower() + first_para[1:] if first_para else ''}\n")
        else:
            base_name = Path(clean_target).stem.replace("_", " ").title()
            init_msg = initial_commit["message"].splitlines()[0] if initial_commit else "initial repository development"
            sections.append(
                f"**What it does**:\n`{clean_target}` serves as the module for **{base_name}**, "
                f"providing foundational logic originally created to support: _{init_msg}_.\n"
            )

        # Architectural Component Role
        sections.append("#### Architecture & Component Role")
        arch_items = []
        if classes_count > 0 or functions_count > 0:
            arch_items.append(f"- **Structure**: Implements **{classes_count} class{'es' if classes_count != 1 else ''}** and **{functions_count} function{'s' if functions_count != 1 else ''}**.")

        if deps.get("upstream"):
            top_up = [Path(p).name for p in deps["upstream"][:5]]
            arch_items.append(f"- **Depends on**: `{', '.join(top_up)}`")

        if deps.get("downstream"):
            top_down = [Path(p).name for p in deps["downstream"][:5]]
            arch_items.append(f"- **Consumed by**: `{', '.join(top_down)}`")

        if not arch_items:
            arch_items.append("- Self-contained utility module with localized scope.")

        sections.append("\n".join(arch_items) + "\n")

        # Historical Rationale & Evolution
        sections.append("#### Historical Rationale & Evolution")
        history_items = []
        if initial_commit:
            history_items.append(
                f"- **Origination**: Introduced in commit `{initial_commit['commit_sha'][:8]}` by **{initial_commit['author_name']}** with message: \"{initial_commit['message']}\"."
            )

        if latest_commit and latest_commit != initial_commit:
            history_items.append(
                f"- **Latest Evolution**: Last modified in commit `{latest_commit['commit_sha'][:8]}`: \"{latest_commit['message']}\" (+{latest_commit['lines_added']}/-{latest_commit['lines_removed']} lines)."
            )

        if co_changes:
            top_co = [f"`{c['file']}` ({c['co_change_count']}x)" for c in co_changes[:4]]
            history_items.append(f"- **Frequent Co-changes**: Often evolved alongside {', '.join(top_co)}.")

        for sr in search_results:
            if sr.doc_type.value == "docstring" and sr.text:
                history_items.append(f"- **Documented Design**: {sr.text.splitlines()[-1]}")

        sections.append("\n".join(history_items))

        return "\n".join(sections)

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node execution for Historian."""
        target = state.get("target") or "repository"
        query = state.get("query", "")
        response = self.explain(target, query)
        return {
            "explain_response": response,
            "status": "historian_completed",
        }
