"""Agents package for Supervisor, Historian, Impact, Proposer, Critic, and Onboarding."""

from codebase_historian.agents.schemas import (
    Citation,
    CriticVerdict,
    ExplainRequest,
    ExplainResponse,
    ImpactRequest,
    ImpactResponse,
    RefactorRequest,
    RefactorResponse,
    OnboardingRequest,
    OnboardingResponse,
)
from codebase_historian.agents.state import AgentState
from codebase_historian.agents.supervisor import SupervisorAgent
from codebase_historian.agents.historian import HistorianAgent
from codebase_historian.agents.impact import ImpactAgent
from codebase_historian.agents.onboarding import OnboardingAgent
from codebase_historian.agents.refactor import (
    RefactorProposerAgent,
    CriticAgent,
    human_review_gate,
)
from codebase_historian.agents.orchestrator import HistorianOrchestrator

__all__ = [
    "Citation",
    "CriticVerdict",
    "ExplainRequest",
    "ExplainResponse",
    "ImpactRequest",
    "ImpactResponse",
    "RefactorRequest",
    "RefactorResponse",
    "OnboardingRequest",
    "OnboardingResponse",
    "AgentState",
    "SupervisorAgent",
    "HistorianAgent",
    "ImpactAgent",
    "OnboardingAgent",
    "RefactorProposerAgent",
    "CriticAgent",
    "human_review_gate",
    "HistorianOrchestrator",
]
