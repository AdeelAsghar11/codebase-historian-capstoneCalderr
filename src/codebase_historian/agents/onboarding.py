"""
Onboarding agent.
Generates starting guides, centrality-ranked reading orders, and traced architectural decisions.
"""

from typing import Any

from codebase_historian.agents.schemas import OnboardingResponse
from codebase_historian.agents.state import AgentState
from codebase_historian.graph.graph import CodebaseKnowledgeGraph


class OnboardingAgent:
    """Generates contributor onboarding guides using graph centrality and history."""

    def __init__(self, knowledge_graph: CodebaseKnowledgeGraph | None = None):
        self.kg = knowledge_graph

    def generate_guide(self) -> OnboardingResponse:
        """Generate reading order, central files, and key decisions."""
        if not self.kg:
            return OnboardingResponse(
                reading_order=[],
                central_files=[],
                key_decisions=["No repository graph loaded."],
            )

        central_data = self.kg.get_central_files(top_n=10)
        central_files = [item["file"] for item in central_data]

        # Reading order: core central files first, then remaining
        reading_order = central_files.copy()

        key_decisions = []
        # Find PRs in graph
        for node_id, data in self.kg.g.nodes(data=True):
            if data.get("type") == "PullRequest":
                title = data.get("title", "")
                num = data.get("number", "")
                key_decisions.append(f"PR #{num}: {title}")

        if not key_decisions:
            # Fallback to initial commits
            for node_id, data in self.kg.g.nodes(data=True):
                if data.get("type") == "Commit" and not data.get("parent_shas"):
                    key_decisions.append(f"Root commit: {data.get('message', '')}")

        return OnboardingResponse(
            reading_order=reading_order,
            central_files=central_files,
            key_decisions=key_decisions[:5],
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node execution for Onboarding agent."""
        response = self.generate_guide()
        return {
            "onboarding_response": response,
            "status": "onboarding_completed",
        }
