"""
Unified service layer for Codebase Historian.
Used by both the FastAPI REST API and Typer CLI.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from codebase_historian.agents.orchestrator import HistorianOrchestrator
from codebase_historian.agents.schemas import (
    ExplainResponse,
    ImpactResponse,
    OnboardingResponse,
    RefactorResponse,
)
from codebase_historian.config import settings
from codebase_historian.graph.builder import KnowledgeGraphBuilder
from codebase_historian.graph.graph import CodebaseKnowledgeGraph
from codebase_historian.ingestion.pipeline import IngestionPipeline, IngestionResult
from codebase_historian.memory.store import SQLiteMemoryStore
from codebase_historian.retrieval.hybrid_index import HybridRetrievalIndex


class HistorianService:
    """Coordinates ingestion, storage, graph, index, and agent execution."""

    def __init__(
        self,
        repo_path: str = ".",
        db_path: Optional[str] = None,
        chroma_path: Optional[str] = None,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.db_path = db_path or settings.db_path
        self.chroma_path = chroma_path or settings.chroma_db_path

        self.memory_store = SQLiteMemoryStore(db_path=self.db_path)
        self.retrieval_index = HybridRetrievalIndex(persist_directory=self.chroma_path)
        self.knowledge_graph = CodebaseKnowledgeGraph()

        # Check if graph file exists locally to load
        self.graph_file = Path(self.repo_path) / ".codebase_graph.json"
        if self.graph_file.exists():
            try:
                self.knowledge_graph = CodebaseKnowledgeGraph.load(self.graph_file)
            except Exception:
                pass

        self.orchestrator = HistorianOrchestrator(
            knowledge_graph=self.knowledge_graph,
            retrieval_index=self.retrieval_index,
            memory_store=self.memory_store,
        )

    def ingest(self, repo_path: Optional[str] = None) -> IngestionResult:
        """Run repository ingestion, populate knowledge graph and hybrid index."""
        target_path = Path(repo_path).resolve() if repo_path else self.repo_path
        pipeline = IngestionPipeline(target_path)
        result = pipeline.run()

        # Populate knowledge graph
        builder = KnowledgeGraphBuilder(self.knowledge_graph)
        self.knowledge_graph = builder.build_from_ingestion(result)

        # Save graph for persistence
        try:
            self.knowledge_graph.save(self.graph_file)
        except Exception:
            pass

        # Populate hybrid retrieval index
        self.retrieval_index.index_ingestion_result(result)

        # Update index state in SQLite
        if result.last_indexed_commit_sha:
            self.memory_store.set_index_state(
                str(target_path), result.last_indexed_commit_sha
            )

        # Re-initialize orchestrator with updated components
        self.orchestrator = HistorianOrchestrator(
            knowledge_graph=self.knowledge_graph,
            retrieval_index=self.retrieval_index,
            memory_store=self.memory_store,
        )

        return result

    def explain(self, target: str, repo_url: Optional[str] = None) -> ExplainResponse:
        """Route to Historian agent to explain a target."""
        state = self.orchestrator.run(
            query=f"Why does {target} exist?",
            target=target,
            repo_url=repo_url,
        )
        return state.get("explain_response") or ExplainResponse(
            answer="Unable to explain target.", confidence=0.0
        )

    def impact(self, change_description: str, repo_url: Optional[str] = None) -> ImpactResponse:
        """Route to Impact / Risk agent."""
        state = self.orchestrator.run(
            query=change_description,
            repo_url=repo_url,
        )
        return state.get("impact_response") or ImpactResponse(
            affected_files=[], confidence=0.0, evidence="co-change"
        )

    def suggest_refactor(self, target: str, repo_url: Optional[str] = None) -> RefactorResponse:
        """Route to Refactor Proposer <-> Critic debate loop."""
        state = self.orchestrator.run(
            query=f"Refactor {target}",
            target=target,
            repo_url=repo_url,
        )
        return state.get("refactor_response") or RefactorResponse(
            proposal="No proposal generated",
            critic_verdict={"refuted": True, "notes": "No critique"},
            status="rejected_by_critic",
        )

    def onboarding_guide(self, repo_url: Optional[str] = None) -> OnboardingResponse:
        """Route to Onboarding agent."""
        state = self.orchestrator.run(
            query="Generate onboarding guide",
            repo_url=repo_url,
        )
        return state.get("onboarding_response") or OnboardingResponse()

    def health(self) -> Dict[str, Any]:
        """Return system health and index freshness."""
        idx_state = self.memory_store.get_index_state(str(self.repo_path))
        summary = self.knowledge_graph.summary()

        return {
            "status": "healthy",
            "last_indexed_commit": idx_state.last_indexed_commit_sha if idx_state else None,
            "graph_node_count": summary["total_nodes"],
            "graph_edge_count": summary["total_edges"],
            "indexed_documents_count": self.retrieval_index.count(),
            "degraded": False,
        }
