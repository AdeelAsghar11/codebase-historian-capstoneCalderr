"""
Schema-validated request and response models for all agents.
Follows naming conventions in CONVENTIONS.md (Request / Response suffixes).
"""

from typing import Literal

from pydantic import BaseModel, Field

# --- Shared Sub-models ---

class Citation(BaseModel):
    commit_sha: str | None = None
    pr_number: int | None = None
    excerpt: str


class CriticVerdict(BaseModel):
    refuted: bool
    notes: str


# --- Historian Agent Schemas ---

class ExplainRequest(BaseModel):
    repo_url: str | None = None
    target: str = Field(..., description="File path or symbol qualname to explain")


class ExplainResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


# --- Impact / Risk Agent Schemas ---

class ImpactRequest(BaseModel):
    repo_url: str | None = None
    change_description: str = Field(
        ..., description="Diff or plain-language description of proposed change"
    )


class ImpactResponse(BaseModel):
    affected_files: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    evidence: Literal["co-change", "dependency", "both"] = "both"


# --- Refactor Proposer ↔ Critic Schemas ---

class RefactorRequest(BaseModel):
    repo_url: str | None = None
    target: str = Field(..., description="File path or symbol to propose refactor for")


class RefactorResponse(BaseModel):
    proposal: str
    critic_verdict: CriticVerdict
    status: Literal["pending_human_review", "rejected_by_critic"] = "pending_human_review"


# --- Onboarding Agent Schemas ---

class OnboardingRequest(BaseModel):
    repo_url: str | None = None


class OnboardingResponse(BaseModel):
    reading_order: list[str] = Field(default_factory=list)
    central_files: list[str] = Field(default_factory=list)
    key_decisions: list[str] = Field(default_factory=list)
