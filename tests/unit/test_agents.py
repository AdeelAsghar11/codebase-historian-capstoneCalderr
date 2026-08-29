"""
Unit tests for the Agent Team, Supervisor routing, Refactor Proposer <-> Critic debate,
mandatory human approval gate, and LangGraph state graph execution.
"""

from datetime import datetime, timezone
import pytest

from codebase_historian.agents import (
    CriticAgent,
    HistorianAgent,
    HistorianOrchestrator,
    ImpactAgent,
    OnboardingAgent,
    RefactorProposerAgent,
    SupervisorAgent,
    human_review_gate,
)
from codebase_historian.agents.schemas import CriticVerdict
from codebase_historian.agents.state import AgentState
from codebase_historian.graph.builder import KnowledgeGraphBuilder
from codebase_historian.graph.graph import CodebaseKnowledgeGraph
from codebase_historian.ingestion.models import (
    AuthorRecord,
    CommitRecord,
    FileModificationRecord,
    CoChangeRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.pipeline import IngestionResult
from codebase_historian.memory.store import SQLiteMemoryStore
from codebase_historian.retrieval.hybrid_index import HybridRetrievalIndex


@pytest.fixture
def populated_components():
    """Build a connected mock environment with Graph, Index, and Memory."""
    author = AuthorRecord(id="dev@example.com", display_name="Lead Dev")
    c1 = CommitRecord(
        sha="commit_sha_123",
        author=author,
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        message="feat: core authentication service",
        modifications=[
            FileModificationRecord(path="src/auth.py", change_type="A", lines_added=80)
        ],
    )
    c2 = CommitRecord(
        sha="commit_sha_456",
        author=author,
        timestamp=datetime(2026, 1, 20, 15, 0, tzinfo=timezone.utc),
        message="feat: user service depending on auth",
        modifications=[
            FileModificationRecord(path="src/user.py", change_type="A", lines_added=60),
            FileModificationRecord(path="src/auth.py", change_type="M", lines_added=5),
        ],
    )
    co_change = CoChangeRecord(
        file_a="src/auth.py",
        file_b="src/user.py",
        co_change_count=2,
        last_co_change_commit="commit_sha_456",
    )
    structures = [
        FileStructureRecord(path="src/auth.py", docstring="Authentication provider module."),
        FileStructureRecord(path="src/user.py", docstring="User management and profile service."),
    ]
    deps = [("src/user.py", "src/auth.py", "from")]

    ingest_result = IngestionResult(
        repo_path="/mock/repo",
        commits=[c1, c2],
        co_changes=[co_change],
        file_structures=structures,
        dependencies=deps,
    )

    # 1. Knowledge Graph
    kg = KnowledgeGraphBuilder().build_from_ingestion(ingest_result)

    # 2. Hybrid Index
    index = HybridRetrievalIndex()
    index.index_ingestion_result(ingest_result)

    # 3. Memory Store
    memory = SQLiteMemoryStore(db_path=":memory:")

    return kg, index, memory


def test_supervisor_routing():
    supervisor = SupervisorAgent()

    # Route to historian
    r1, target1 = supervisor.route_query("Why does src/auth.py exist?")
    assert r1 == "historian"
    assert target1 == "src/auth.py"

    # Route to impact
    r2, target2 = supervisor.route_query("What is the blast radius if we modify src/auth.py?")
    assert r2 == "impact"
    assert target2 == "src/auth.py"

    # Route to refactor
    r3, target3 = supervisor.route_query("Please refactor src/user.py to reduce coupling")
    assert r3 == "refactor"
    assert target3 == "src/user.py"

    # Route to onboarding
    r4, _ = supervisor.route_query("Give me an onboarding contributor guide for this codebase")
    assert r4 == "onboarding"


def test_historian_agent(populated_components):
    kg, index, memory = populated_components
    historian = HistorianAgent(knowledge_graph=kg, retrieval_index=index, memory_store=memory)

    response = historian.explain("src/auth.py")
    assert response.confidence > 0.8
    assert len(response.citations) >= 1
    assert any("commit_sha_123" in (c.commit_sha or "") for c in response.citations)
    assert "core authentication service" in response.answer

    # Verify memory was populated
    entries = memory.get_by_subject("src/auth.py")
    assert len(entries) == 1
    assert entries[0].status.value == "active"


def test_impact_agent(populated_components):
    kg, _, _ = populated_components
    impact = ImpactAgent(knowledge_graph=kg)

    response = impact.predict_impact("Modifying authentication tokens in src/auth.py")
    assert "src/user.py" in response.affected_files
    assert response.evidence == "both"
    assert response.confidence >= 0.7


def test_onboarding_agent(populated_components):
    kg, _, _ = populated_components
    onboarding = OnboardingAgent(knowledge_graph=kg)

    guide = onboarding.generate_guide()
    assert len(guide.central_files) == 2
    assert "src/auth.py" in guide.central_files
    assert len(guide.reading_order) == 2


def test_refactor_proposer_critic_adversarial_debate(populated_components):
    kg, _, _ = populated_components
    proposer = RefactorProposerAgent(knowledge_graph=kg)
    critic = CriticAgent(knowledge_graph=kg)

    # Iteration 1: initial proposal
    p1 = proposer.propose("src/auth.py")
    v1 = critic.critique(p1, "src/auth.py", debate_iterations=1)

    # Iteration 2: revised proposal incorporating critique
    p2 = proposer.propose("src/auth.py", critic_feedback=v1.notes)
    v2 = critic.critique(p2, "src/auth.py", debate_iterations=2)

    assert v2.refuted is False
    assert "successfully addresses" in v2.notes


def test_mandatory_human_review_gate_safety():
    """
    CRITICAL NON-NEGOTIABLE SAFETY TEST:
    Asserts that NO proposal can bypass the human review gate or be auto-approved.
    """
    # 1. When Critic approves
    state_approved: AgentState = {
        "refactor_proposal": "Safe modular refactor",
        "critic_verdict": CriticVerdict(refuted=False, notes="Approved by critic"),
    }
    res_approved = human_review_gate(state_approved)
    # MUST be strictly pending_human_review
    assert res_approved["refactor_response"].status == "pending_human_review"
    assert res_approved["status"] == "pending_human_review"

    # 2. When Critic refutes
    state_refuted: AgentState = {
        "refactor_proposal": "Risky refactor",
        "critic_verdict": CriticVerdict(refuted=True, notes="Breaks API"),
    }
    res_refuted = human_review_gate(state_refuted)
    assert res_refuted["refactor_response"].status == "rejected_by_critic"
    assert res_refuted["status"] == "rejected_by_critic"


def test_historian_orchestrator_langgraph_execution(populated_components):
    kg, index, memory = populated_components
    orchestrator = HistorianOrchestrator(
        knowledge_graph=kg,
        retrieval_index=index,
        memory_store=memory,
    )

    # 1. Test Historian Path
    state_hist = orchestrator.run("Why does src/auth.py exist?", target="src/auth.py")
    assert state_hist["route"] == "historian"
    assert state_hist["explain_response"] is not None
    assert len(state_hist["explain_response"].citations) >= 1

    # 2. Test Impact Path
    state_impact = orchestrator.run("What breaks if we change src/auth.py?")
    assert state_impact["route"] == "impact"
    assert state_impact["impact_response"] is not None
    assert "src/user.py" in state_impact["impact_response"].affected_files

    # 3. Test Onboarding Path
    state_onboard = orchestrator.run("How do I onboard to this project?")
    assert state_onboard["route"] == "onboarding"
    assert state_onboard["onboarding_response"] is not None
    assert len(state_onboard["onboarding_response"].central_files) > 0

    # 4. Test Refactor Proposer <-> Critic Debate & Human Gate
    state_refactor = orchestrator.run("Refactor src/auth.py", target="src/auth.py")
    assert state_refactor["route"] == "refactor"
    assert state_refactor["refactor_response"] is not None
    assert state_refactor["refactor_response"].status == "pending_human_review"
    assert state_refactor["refactor_response"].critic_verdict.refuted is False
    assert state_refactor["debate_iterations"] >= 1
