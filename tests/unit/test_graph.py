"""
Unit tests for the CodebaseKnowledgeGraph and KnowledgeGraphBuilder.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from codebase_historian.ingestion.models import (
    AuthorRecord,
    CommitRecord,
    FileModificationRecord,
    CoChangeRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.pipeline import IngestionResult
from codebase_historian.graph.models import (
    NodeType,
    EdgeType,
    PullRequestNodeData,
    IssueNodeData,
)
from codebase_historian.graph.graph import CodebaseKnowledgeGraph
from codebase_historian.graph.builder import KnowledgeGraphBuilder


@pytest.fixture
def sample_ingestion_result() -> IngestionResult:
    """Fixture providing a mock IngestionResult."""
    author1 = AuthorRecord(id="alice@example.com", display_name="Alice")
    author2 = AuthorRecord(id="bob@example.com", display_name="Bob")

    c1 = CommitRecord(
        sha="sha_001",
        author=author1,
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        message="feat: initial commit with auth",
        parent_shas=[],
        modifications=[
            FileModificationRecord(
                path="src/auth.py",
                change_type="A",
                lines_added=50,
                lines_removed=0,
                diff_summary="Add auth module",
            )
        ],
    )

    c2 = CommitRecord(
        sha="sha_002",
        author=author2,
        timestamp=datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc),
        message="feat: add user service depending on auth",
        parent_shas=["sha_001"],
        modifications=[
            FileModificationRecord(
                path="src/auth.py",
                change_type="M",
                lines_added=10,
                lines_removed=2,
                diff_summary="Update auth tokens",
            ),
            FileModificationRecord(
                path="src/user.py",
                change_type="A",
                lines_added=100,
                lines_removed=0,
                diff_summary="Add user service",
            ),
        ],
    )

    co_change = CoChangeRecord(
        file_a="src/auth.py",
        file_b="src/user.py",
        co_change_count=1,
        last_co_change_commit="sha_002",
    )

    fs_auth = FileStructureRecord(path="src/auth.py", language="python")
    fs_user = FileStructureRecord(path="src/user.py", language="python")

    # src/user.py depends on src/auth.py
    deps = [("src/user.py", "src/auth.py", "from")]

    return IngestionResult(
        repo_path="/mock/repo",
        last_indexed_commit_sha="sha_002",
        commits=[c1, c2],
        co_changes=[co_change],
        file_structures=[fs_auth, fs_user],
        dependencies=deps,
        stats={"total_commits": 2},
    )


def test_knowledge_graph_builder_and_structure(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    summary = kg.summary()
    assert summary["total_nodes"] >= 4  # 2 files, 2 commits, 2 authors
    assert summary["nodes_by_type"].get(NodeType.FILE.value) == 2
    assert summary["nodes_by_type"].get(NodeType.COMMIT.value) == 2
    assert summary["nodes_by_type"].get(NodeType.AUTHOR.value) == 2

    # Check edges
    edges = summary["edges_by_type"]
    assert edges.get(EdgeType.MODIFIES.value) == 3  # c1 -> auth, c2 -> auth, c2 -> user
    assert edges.get(EdgeType.AUTHORED_BY.value) == 2
    assert edges.get(EdgeType.CO_CHANGES_WITH.value) == 2  # Bidirectional
    assert edges.get(EdgeType.DEPENDS_ON.value) == 1  # user -> auth


def test_get_file_history(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    auth_history = kg.get_file_history("src/auth.py")
    assert len(auth_history) == 2
    assert auth_history[0]["commit_sha"] == "sha_001"
    assert auth_history[0]["lines_added"] == 50
    assert auth_history[1]["commit_sha"] == "sha_002"
    assert auth_history[1]["lines_added"] == 10
    assert auth_history[1]["lines_removed"] == 2

    user_history = kg.get_file_history("src/user.py")
    assert len(user_history) == 1
    assert user_history[0]["commit_sha"] == "sha_002"


def test_get_file_co_changes(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    co_changes = kg.get_file_co_changes("src/auth.py")
    assert len(co_changes) == 1
    assert co_changes[0]["file"] == "src/user.py"
    assert co_changes[0]["co_change_count"] == 1
    assert co_changes[0]["last_commit"] == "sha_002"


def test_get_file_dependencies(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    user_deps = kg.get_file_dependencies("src/user.py")
    assert "src/auth.py" in user_deps["imports"]

    auth_deps = kg.get_file_dependencies("src/auth.py")
    assert "src/user.py" in auth_deps["imported_by"]


def test_blast_radius_prediction(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    # When src/auth.py is modified, src/user.py should be predicted with "both" evidence
    # (since it imports auth.py AND historically co-changed with it)
    blast = kg.get_blast_radius(["src/auth.py"])
    assert len(blast) == 1
    assert blast[0]["file"] == "src/user.py"
    assert blast[0]["evidence"] == "both"
    assert blast[0]["confidence"] >= 0.70


def test_graph_centrality_and_ranking(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    central_files = kg.get_central_files(top_n=5)
    assert len(central_files) == 2
    # auth.py should be more central than user.py (imported by user, co-changed with user)
    paths = [f["file"] for f in central_files]
    assert "src/auth.py" in paths
    assert "src/user.py" in paths


def test_pull_request_and_issue_integration(sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    # Add Issue
    builder.add_issue(
        IssueNodeData(
            number=42,
            title="User authentication token expiration",
            body="Tokens should expire after 24h",
            author="alice@example.com",
            status="closed",
        )
    )

    # Add PR referencing commit and issue
    builder.add_pull_request(
        PullRequestNodeData(
            number=101,
            title="Add user service and auth token refresh",
            author="bob@example.com",
            status="merged",
        ),
        commit_shas=["sha_002"],
        referenced_issue_numbers=[42],
    )

    summary = kg.summary()
    assert summary["nodes_by_type"].get(NodeType.PULL_REQUEST.value) == 1
    assert summary["nodes_by_type"].get(NodeType.ISSUE.value) == 1
    assert summary["edges_by_type"].get(EdgeType.INCLUDES.value) == 1
    assert summary["edges_by_type"].get(EdgeType.REFERENCES.value) == 1


def test_graph_serialization_roundtrip(tmp_path: Path, sample_ingestion_result):
    builder = KnowledgeGraphBuilder()
    kg = builder.build_from_ingestion(sample_ingestion_result)

    save_path = tmp_path / "knowledge_graph.json"
    kg.save(save_path)
    assert save_path.exists()

    loaded_kg = CodebaseKnowledgeGraph.load(save_path)
    assert loaded_kg.summary() == kg.summary()
    assert loaded_kg.get_file_history("src/auth.py") == kg.get_file_history("src/auth.py")
