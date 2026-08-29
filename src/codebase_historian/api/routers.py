"""
FastAPI route handlers for /v1 endpoints.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from codebase_historian.agents.schemas import (
    ExplainRequest,
    ExplainResponse,
    ImpactRequest,
    ImpactResponse,
    OnboardingRequest,
    OnboardingResponse,
    RefactorRequest,
    RefactorResponse,
)
from codebase_historian.service import HistorianService

router = APIRouter(prefix="/v1")

# Global or dependency-injected service instance
_service: Optional[HistorianService] = None


def get_service() -> HistorianService:
    global _service
    if _service is None:
        _service = HistorianService()
    return _service


def set_service(service: HistorianService) -> None:
    global _service
    _service = service


class IngestRequest(BaseModel):
    repo_path: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    last_indexed_commit: Optional[str] = None
    graph_node_count: int
    graph_edge_count: int
    indexed_documents_count: int
    degraded: bool


@router.get("/health", response_model=HealthResponse)
def health_check(service: HistorianService = Depends(get_service)):
    """Health check endpoint reporting graph freshness and last-indexed commit."""
    data = service.health()
    return HealthResponse(**data)


@router.post("/explain", response_model=ExplainResponse)
def explain_code(req: ExplainRequest, service: HistorianService = Depends(get_service)):
    """Explain why a file or symbol exists, citing commits and discussions."""
    return service.explain(target=req.target, repo_url=req.repo_url)


@router.post("/impact", response_model=ImpactResponse)
def trace_impact(req: ImpactRequest, service: HistorianService = Depends(get_service)):
    """Predict blast radius and affected files for a proposed change."""
    return service.impact(change_description=req.change_description, repo_url=req.repo_url)


@router.post("/refactor/suggest", response_model=RefactorResponse)
def suggest_refactor(req: RefactorRequest, service: HistorianService = Depends(get_service)):
    """Propose refactor via Proposer <-> Critic debate under mandatory human review gate."""
    return service.suggest_refactor(target=req.target, repo_url=req.repo_url)


@router.post("/onboarding/guide", response_model=OnboardingResponse)
def onboarding_guide(req: OnboardingRequest, service: HistorianService = Depends(get_service)):
    """Generate contributor onboarding guide with central files and reading order."""
    return service.onboarding_guide(repo_url=req.repo_url)


@router.post("/ingest")
def ingest_repository(req: IngestRequest, service: HistorianService = Depends(get_service)):
    """Ingest git history and AST structure for a repository."""
    res = service.ingest(req.repo_path)
    return {
        "status": "success",
        "last_indexed_commit": res.last_indexed_commit_sha,
        "stats": res.stats,
    }
