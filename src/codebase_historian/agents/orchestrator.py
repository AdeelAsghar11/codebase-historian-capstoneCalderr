"""
LangGraph state graph orchestrator.
Assembles Supervisor router, specialist agents (Historian, Impact, Onboarding),
and the adversarial Refactor Proposer <-> Critic debate loop under a mandatory human gate.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from codebase_historian.agents.historian import HistorianAgent
from codebase_historian.agents.impact import ImpactAgent
from codebase_historian.agents.onboarding import OnboardingAgent
from codebase_historian.agents.refactor import (
    CriticAgent,
    RefactorProposerAgent,
    human_review_gate,
)
from codebase_historian.agents.state import AgentState
from codebase_historian.agents.supervisor import SupervisorAgent
from codebase_historian.graph.graph import CodebaseKnowledgeGraph
from codebase_historian.memory.store import SQLiteMemoryStore
from codebase_historian.retrieval.hybrid_index import HybridRetrievalIndex


def route_decision(state: AgentState) -> str:
    """Routing edge function from supervisor."""
    route = state.get("route", "historian")
    if route == "impact":
        return "impact_node"
    elif route == "refactor":
        return "proposer_node"
    elif route == "onboarding":
        return "onboarding_node"
    return "historian_node"


def critic_decision(state: AgentState) -> str:
    """Adversarial debate conditional edge from Critic."""
    verdict = state.get("critic_verdict")
    iterations = state.get("debate_iterations", 1)

    # If refuted and under max iterations (2 passes), loop back to proposer
    if verdict and verdict.refuted and iterations < 2:
        return "proposer_node"

    return "human_gate_node"


class HistorianOrchestrator:
    """High-level orchestrator wrapping compiled LangGraph state graph."""

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

        # Initialize agents
        self.supervisor = SupervisorAgent(llm=self.llm)
        self.historian = HistorianAgent(
            knowledge_graph=self.kg,
            retrieval_index=self.index,
            memory_store=self.memory,
            llm=self.llm,
        )
        self.impact = ImpactAgent(knowledge_graph=self.kg)
        self.onboarding = OnboardingAgent(knowledge_graph=self.kg)
        self.proposer = RefactorProposerAgent(knowledge_graph=self.kg)
        self.critic = CriticAgent(knowledge_graph=self.kg)

        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Construct and compile the LangGraph StateGraph."""
        builder = StateGraph(AgentState)

        # Add Nodes
        builder.add_node("supervisor_node", self.supervisor)
        builder.add_node("historian_node", self.historian)
        builder.add_node("impact_node", self.impact)
        builder.add_node("onboarding_node", self.onboarding)
        builder.add_node("proposer_node", self.proposer)
        builder.add_node("critic_node", self.critic)
        builder.add_node("human_gate_node", human_review_gate)

        # Add Edges
        builder.add_edge(START, "supervisor_node")

        # Supervisor routing edge
        builder.add_conditional_edges(
            "supervisor_node",
            route_decision,
            {
                "historian_node": "historian_node",
                "impact_node": "impact_node",
                "onboarding_node": "onboarding_node",
                "proposer_node": "proposer_node",
            },
        )

        # Direct response paths
        builder.add_edge("historian_node", END)
        builder.add_edge("impact_node", END)
        builder.add_edge("onboarding_node", END)

        # Refactor debate loop
        builder.add_edge("proposer_node", "critic_node")
        builder.add_conditional_edges(
            "critic_node",
            critic_decision,
            {
                "proposer_node": "proposer_node",
                "human_gate_node": "human_gate_node",
            },
        )
        builder.add_edge("human_gate_node", END)

        return builder.compile()

    def run(
        self,
        query: str,
        target: str | None = None,
        repo_url: str | None = None,
    ) -> AgentState:
        """Execute the workflow for a given query."""
        initial_state: AgentState = {
            "query": query,
            "target": target,
            "repo_url": repo_url,
            "debate_iterations": 0,
            "status": "started",
        }
        return self.graph.invoke(initial_state)
