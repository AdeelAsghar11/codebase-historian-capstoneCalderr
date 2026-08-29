"""
State definition for the LangGraph agent workflow.
"""

from typing import Any, Dict, List, Optional, TypedDict
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
    target: Optional[str]
    repo_url: Optional[str]

    # Routing decision
    route: Optional[str]  # "historian", "impact", "refactor", "onboarding"

    # Retrieved context (from KnowledgeGraph, HybridIndex, or Memory)
    context: Dict[str, Any]

    # Agent outputs
    explain_response: Optional[ExplainResponse]
    impact_response: Optional[ImpactResponse]
    onboarding_response: Optional[OnboardingResponse]

    # Refactor debate loop state
    refactor_proposal: Optional[str]
    critic_verdict: Optional[CriticVerdict]
    refactor_response: Optional[RefactorResponse]
    debate_iterations: int

    # Overall execution status
    status: str
    error: Optional[str]
