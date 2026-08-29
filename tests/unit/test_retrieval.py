"""
Unit tests for the HybridRetrievalIndex and LexicalMatcher.
"""

from datetime import UTC, datetime
from pathlib import Path

from codebase_historian.graph.models import PullRequestNodeData
from codebase_historian.ingestion.models import (
    ASTClassRecord,
    ASTFunctionRecord,
    AuthorRecord,
    CommitRecord,
    FileModificationRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.pipeline import IngestionResult
from codebase_historian.retrieval.hybrid_index import (
    HybridRetrievalIndex,
    LexicalMatcher,
)
from codebase_historian.retrieval.models import DocumentType, IndexedDocument


def test_lexical_matcher():
    matcher = LexicalMatcher()
    docs = [
        IndexedDocument(
            id="doc1",
            text="User authentication service using JWT tokens",
            doc_type=DocumentType.COMMIT,
            subject="src/auth.py",
        ),
        IndexedDocument(
            id="doc2",
            text="PostgreSQL database connection pool and retry logic",
            doc_type=DocumentType.COMMIT,
            subject="src/db.py",
        ),
    ]
    matcher.add_documents(docs)

    # Search for authentication
    scores_auth = matcher.score("JWT authentication")
    assert "doc1" in scores_auth
    assert scores_auth["doc1"] > scores_auth.get("doc2", 0.0)

    # Search for database
    scores_db = matcher.score("database connection")
    assert "doc2" in scores_db
    assert scores_db["doc2"] > scores_db.get("doc1", 0.0)


def test_hybrid_index_indexing_commits():
    index = HybridRetrievalIndex()  # In-memory ephemeral
    commits = [
        CommitRecord(
            sha="c1_sha",
            author=AuthorRecord(id="alice@example.com", display_name="Alice"),
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            message="feat: implement OAuth2 authentication provider",
            modifications=[
                FileModificationRecord(path="src/auth/oauth.py", change_type="A")
            ],
        ),
        CommitRecord(
            sha="c2_sha",
            author=AuthorRecord(id="bob@example.com", display_name="Bob"),
            timestamp=datetime(2026, 1, 2, 14, 0, tzinfo=UTC),
            message="fix: resolve memory leak in background worker task queue",
            modifications=[
                FileModificationRecord(path="src/worker/queue.py", change_type="M")
            ],
        ),
    ]

    index.index_commits(commits)
    assert index.count() == 2

    # Query for OAuth
    results = index.search("OAuth2 authentication", top_k=2)
    assert len(results) >= 1
    top = results[0]
    assert top.id == "commit:c1_sha"
    assert top.doc_type == DocumentType.COMMIT
    assert top.score > 0.0
    assert "OAuth2 authentication" in top.text


def test_hybrid_index_pr_and_docstrings():
    index = HybridRetrievalIndex()

    prs = [
        PullRequestNodeData(
            number=42,
            title="Refactor Graph Neural Network embedding pipeline",
            description="Replaces legacy embedding lookup with batched tensor inference.",
            author="charlie@example.com",
            status="merged",
        )
    ]

    structures = [
        FileStructureRecord(
            path="src/graph/embeddings.py",
            docstring="Module for computing node embeddings in the codebase graph.",
            classes=[
                ASTClassRecord(
                    name="Embedder",
                    qualname="Embedder",
                    docstring="Generates vector embeddings for code symbols and AST nodes.",
                    start_line=10,
                    end_line=50,
                    methods=[
                        ASTFunctionRecord(
                            name="embed_query",
                            qualname="Embedder.embed_query",
                            docstring="Embeds a query text into a 384-dimensional vector.",
                            start_line=20,
                            end_line=30,
                        )
                    ],
                )
            ],
            functions=[
                ASTFunctionRecord(
                    name="cosine_sim",
                    qualname="cosine_sim",
                    docstring="Calculates cosine similarity between two float vectors.",
                    start_line=60,
                    end_line=70,
                )
            ],
        )
    ]

    index.index_pull_requests(prs)
    index.index_file_structures(structures)

    # 1 PR + 1 module docstring + 1 class docstring + 1 method docstring + 1 function docstring = 5 docs
    assert index.count() == 5

    # Test filtering by doc_type
    pr_results = index.search("embedding", doc_type=DocumentType.PULL_REQUEST)
    assert len(pr_results) == 1
    assert pr_results[0].id == "pr:42"

    # Test docstring search
    doc_results = index.search("cosine similarity", doc_type=DocumentType.DOCSTRING)
    assert len(doc_results) >= 1
    assert "cosine_sim" in doc_results[0].subject


def test_hybrid_index_persistence(tmp_path: Path):
    persist_dir = tmp_path / "chroma_test"
    index1 = HybridRetrievalIndex(persist_directory=persist_dir)

    commits = [
        CommitRecord(
            sha="persisted_sha",
            author=AuthorRecord(id="dev@example.com", display_name="Dev"),
            timestamp=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
            message="docs: update architecture decision records",
            modifications=[
                FileModificationRecord(path="docs/DECISIONS.md", change_type="M")
            ],
        )
    ]
    index1.index_commits(commits)
    assert index1.count() == 1

    # Search in initial instance
    r1 = index1.search("architecture decision")
    assert len(r1) == 1
    assert r1[0].id == "commit:persisted_sha"


def test_index_full_ingestion_result():
    index = HybridRetrievalIndex()

    author = AuthorRecord(id="alice@example.com", display_name="Alice")
    commits = [
        CommitRecord(
            sha="sha_pipeline",
            author=author,
            timestamp=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            message="feat: pipeline integration test commit",
            modifications=[FileModificationRecord(path="pipeline.py", change_type="A")],
        )
    ]
    structures = [
        FileStructureRecord(
            path="pipeline.py",
            docstring="Orchestrates ingestion and processing.",
        )
    ]
    ingest_result = IngestionResult(
        repo_path="/repo",
        last_indexed_commit_sha="sha_pipeline",
        commits=commits,
        file_structures=structures,
    )

    index.index_ingestion_result(ingest_result)
    assert index.count() == 2

    res = index.search("Orchestrates ingestion")
    assert len(res) >= 1
    assert res[0].doc_type == DocumentType.DOCSTRING
