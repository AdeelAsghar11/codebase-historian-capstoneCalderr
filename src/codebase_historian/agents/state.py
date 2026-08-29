"""
State definition for the LangGraph agent workflow.
"""

from typing import Any, TypedDict

from codebase_historian.agents.schemas import (
    CriticVerdict,
    ExplainResponse,
    ImpactResponse,
    OnboardingResponse,
    RefactorResponse,
)


class AgentState(TypedDict, total=False):
    # Input query & targeting
    query: str
    target: str | None
    repo_url: str | None

    # Routing decision
    route: str | None  # "historian", "impact", "refactor", "onboarding"

    # Retrieved context (from KnowledgeGraph, HybridIndex, or Memory)
    context: dict[str, Any]

    # Agent outputs
    explain_response: ExplainResponse | None
    impact_response: ImpactResponse | None
    onboarding_response: OnboardingResponse | None

    # Refactor debate loop state
    refactor_proposal: str | None
    critic_verdict: CriticVerdict | None
    refactor_response: RefactorResponse | None
    debate_iterations: int

    # Overall execution status
    status: str
    error: str | None
