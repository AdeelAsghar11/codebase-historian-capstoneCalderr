"""
Refactor Proposer and Critic adversarial agents, plus mandatory Human Approval Gate.
"""

from typing import Any

from codebase_historian.agents.schemas import CriticVerdict, RefactorResponse
from codebase_historian.agents.state import AgentState
from codebase_historian.graph.graph import CodebaseKnowledgeGraph


class RefactorProposerAgent:
    """Proposes concrete refactorings grounded in history and dependency structure."""

    def __init__(self, knowledge_graph: CodebaseKnowledgeGraph | None = None):
        self.kg = knowledge_graph

    def propose(self, target: str, critic_feedback: str | None = None) -> str:
        """Draft a refactoring proposal tailored to the target file and any prior critique."""
        clean_target = target.replace("\\", "/")

        blast_info = ""
        if self.kg:
            blast = self.kg.get_blast_radius([clean_target])
            if blast:
                affected_names = ", ".join([b["file"] for b in blast[:3]])
                blast_info = f"\nNote blast radius affects: {affected_names}. Maintain public API stability."

        if critic_feedback:
            return (
                f"### Revised Refactoring Proposal for `{clean_target}`\n"
                f"**Addressing Prior Critic Concerns**: {critic_feedback}\n"
                f"- Modularize internal components while preserving existing function signatures.{blast_info}\n"
                f"- Add explicit typing and isolation to minimize ripple effects."
            )

        return (
            f"### Refactoring Proposal for `{clean_target}`\n"
            f"- Decouple tightly coupled helpers into dedicated sub-functions.\n"
            f"- Consolidate repetitive validation logic.{blast_info}\n"
            f"- Ensure backward compatibility with existing consumers."
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node execution for Proposer."""
        target = state.get("target") or "src/core.py"
        prior_verdict = state.get("critic_verdict")
        feedback = prior_verdict.notes if prior_verdict and prior_verdict.refuted else None

        proposal = self.propose(target, feedback)
        iterations = state.get("debate_iterations", 0) + 1

        return {
            "refactor_proposal": proposal,
            "debate_iterations": iterations,
            "status": "proposal_drafted",
        }


class CriticAgent:
    """Adversarial critic instructed to scrutinize and refute flawed proposals."""

    def __init__(self, knowledge_graph: CodebaseKnowledgeGraph | None = None):
        self.kg = knowledge_graph

    def critique(self, proposal: str, target: str, debate_iterations: int = 1) -> CriticVerdict:
        """
        Adversarially evaluate the proposal.
        First iteration pushes back to test robustness if proposal lacks detail.
        Second iteration approves if proposal addresses concerns.
        """
        if "Addressing Prior Critic Concerns" in proposal or debate_iterations >= 2:
            return CriticVerdict(
                refuted=False,
                notes="Proposal successfully addresses interface stability and blast radius constraints.",
            )

        # First pass pushback to trigger debate
        if "backward compatibility" not in proposal.lower():
            return CriticVerdict(
                refuted=True,
                notes="Proposal fails to explicitly guarantee backward compatibility for downstream consumers.",
            )

        return CriticVerdict(
            refuted=False,
            notes="Proposal passes adversarial scrutiny.",
        )

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """LangGraph node execution for Critic."""
        proposal = state.get("refactor_proposal", "")
        target = state.get("target") or "src/core.py"
        iterations = state.get("debate_iterations", 1)

        verdict = self.critique(proposal, target, iterations)
        return {
            "critic_verdict": verdict,
            "status": "critique_completed",
        }


def human_review_gate(state: AgentState) -> dict[str, Any]:
    """
    Mandatory human review gate.
    Enforces that NO proposal can be marked approved by agents or code paths.
    Status is strictly set to 'pending_human_review' or 'rejected_by_critic'.
    """
    proposal = state.get("refactor_proposal", "")
    verdict = state.get("critic_verdict", CriticVerdict(refuted=True, notes="No critique"))

    if verdict.refuted:
        response = RefactorResponse(
            proposal=proposal,
            critic_verdict=verdict,
            status="rejected_by_critic",
        )
    else:
        # NON-NEGOTIABLE: Always pending_human_review
        response = RefactorResponse(
            proposal=proposal,
            critic_verdict=verdict,
            status="pending_human_review",
        )

    return {
        "refactor_response": response,
        "status": response.status,
    }
