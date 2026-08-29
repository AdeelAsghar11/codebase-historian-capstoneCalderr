"""
Unit tests for the SQLiteMemoryStore and MemoryReconciler (add / update / delete / no-op).
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from codebase_historian.ingestion.models import (
    AuthorRecord,
    CommitRecord,
    FileModificationRecord,
)
from codebase_historian.memory.models import (
    MemoryStatus,
    ReconciliationAction,
)
from codebase_historian.memory.store import SQLiteMemoryStore
from codebase_historian.memory.reconciler import MemoryReconciler


@pytest.fixture
def memory_store():
    """In-memory SQLite database fixture."""
    store = SQLiteMemoryStore(db_path=":memory:")
    yield store
    store.close()


def test_sqlite_store_crud_and_tables(memory_store):
    # 1. Add Entry
    entry = memory_store.add_entry(
        subject="src/auth.py",
        claim_text="Handles JWT authentication and token verification.",
        source_commit_sha="sha_auth_01",
    )
    assert entry.id is not None
    assert entry.subject == "src/auth.py"
    assert entry.status == MemoryStatus.ACTIVE
    assert entry.last_action == ReconciliationAction.ADD

    # 2. Get Entry
    fetched = memory_store.get_entry(entry.id)
    assert fetched is not None
    assert fetched.claim_text == entry.claim_text

    # 3. Get by Subject
    by_subj = memory_store.get_by_subject("src/auth.py")
    assert len(by_subj) == 1

    # 4. Update Entry
    updated = memory_store.update_entry(
        entry.id,
        claim_text="Updated JWT authentication description.",
        status=MemoryStatus.ACTIVE,
        last_action=ReconciliationAction.UPDATE,
    )
    assert updated.claim_text == "Updated JWT authentication description."
    assert updated.last_action == ReconciliationAction.UPDATE

    # 5. Index State
    memory_store.set_index_state("https://github.com/org/repo", "sha_12345")
    idx_state = memory_store.get_index_state("https://github.com/org/repo")
    assert idx_state is not None
    assert idx_state.last_indexed_commit_sha == "sha_12345"

    # 6. Audit Log
    memory_store.log_audit(
        caller_id="user_1",
        tool_name="explain_code",
        endpoint="/explain",
        latency_ms=125,
        status_code=200,
    )
    logs = memory_store.list_audit_logs()
    assert len(logs) == 1
    assert logs[0].caller_id == "user_1"
    assert logs[0].latency_ms == 125


def test_reconciliation_add(memory_store):
    reconciler = MemoryReconciler(memory_store)
    new_explanations = [
        {
            "subject": "src/cache.py",
            "claim_text": "Provides Redis connection caching with TTL fallback.",
            "source_commit_sha": "sha_cache",
        }
    ]

    result = reconciler.reconcile(
        new_commits=[],
        existing_repo_files={"src/cache.py"},
        new_explanations=new_explanations,
    )

    assert result.added == 1
    entries = memory_store.list_entries()
    assert len(entries) == 1
    assert entries[0].subject == "src/cache.py"
    assert entries[0].last_action == ReconciliationAction.ADD
    assert entries[0].status == MemoryStatus.ACTIVE


def test_reconciliation_noop(memory_store):
    reconciler = MemoryReconciler(memory_store)
    e = memory_store.add_entry(
        subject="src/utils.py",
        claim_text="String and date formatting utilities.",
        source_commit_sha="sha_old",
    )

    # Reconcile pass with commit modifying unrelated file
    author = AuthorRecord(id="alice@example.com", display_name="Alice")
    unrelated_commit = CommitRecord(
        sha="sha_new",
        author=author,
        timestamp=datetime.now(timezone.utc),
        message="update auth",
        modifications=[FileModificationRecord(path="src/auth.py", change_type="M")],
    )

    result = reconciler.reconcile(
        new_commits=[unrelated_commit],
        existing_repo_files={"src/utils.py", "src/auth.py"},
    )

    assert result.no_oped == 1
    assert result.updated == 0
    assert result.deleted == 0

    entry = memory_store.get_entry(e.id)
    assert entry.last_action == ReconciliationAction.NO_OP
    assert entry.status == MemoryStatus.ACTIVE


def test_reconciliation_update_with_and_without_callback(memory_store):
    reconciler = MemoryReconciler(memory_store)
    e1 = memory_store.add_entry(
        subject="src/service_a.py",
        claim_text="Initial service A logic.",
        source_commit_sha="sha_a1",
    )
    e2 = memory_store.add_entry(
        subject="src/service_b.py",
        claim_text="Initial service B logic.",
        source_commit_sha="sha_b1",
    )

    author = AuthorRecord(id="bob@example.com", display_name="Bob")
    mod_commit = CommitRecord(
        sha="sha_new_touch",
        author=author,
        timestamp=datetime.now(timezone.utc),
        message="feat: modify service_a and service_b",
        modifications=[
            FileModificationRecord(path="src/service_a.py", change_type="M"),
            FileModificationRecord(path="src/service_b.py", change_type="M"),
        ],
    )

    # Callback that updates service_a but leaves service_b stale
    def updater(entry, commit):
        if "service_a" in entry.subject:
            return f"Regenerated logic based on {commit.sha[:7]}."
        return None

    result = reconciler.reconcile(
        new_commits=[mod_commit],
        existing_repo_files={"src/service_a.py", "src/service_b.py"},
        explanation_updater=updater,
    )

    assert result.updated == 2

    # service_a was regenerated -> ACTIVE with new text
    res_a = memory_store.get_entry(e1.id)
    assert res_a.status == MemoryStatus.ACTIVE
    assert res_a.last_action == ReconciliationAction.UPDATE
    assert "Regenerated" in res_a.claim_text
    assert res_a.source_commit_sha == "sha_new_touch"

    # service_b was not regenerated -> STALE
    res_b = memory_store.get_entry(e2.id)
    assert res_b.status == MemoryStatus.STALE
    assert res_b.last_action == ReconciliationAction.UPDATE
    assert res_b.source_commit_sha == "sha_new_touch"


def test_reconciliation_delete(memory_store):
    reconciler = MemoryReconciler(memory_store)
    e = memory_store.add_entry(
        subject="src/deprecated.py",
        claim_text="Old legacy helper slated for removal.",
        source_commit_sha="sha_old",
    )

    author = AuthorRecord(id="alice@example.com", display_name="Alice")
    del_commit = CommitRecord(
        sha="sha_del",
        author=author,
        timestamp=datetime.now(timezone.utc),
        message="refactor: delete deprecated helper",
        modifications=[FileModificationRecord(path="src/deprecated.py", change_type="D")],
    )

    result = reconciler.reconcile(
        new_commits=[del_commit],
        existing_repo_files=set(),  # File no longer exists in repository
    )

    assert result.deleted == 1
    res = memory_store.get_entry(e.id)
    assert res.status == MemoryStatus.DELETED
    assert res.last_action == ReconciliationAction.DELETE


def test_reconciliation_mixed_all_four_actions(memory_store):
    """Test ADD, UPDATE, DELETE, and NO-OP simultaneously in a single reconciliation pass."""
    reconciler = MemoryReconciler(memory_store)

    # 1. Entry that will be NO-OP
    e_noop = memory_store.add_entry(
        subject="src/stable.py",
        claim_text="Stable core mathematics library.",
        source_commit_sha="sha_stable",
    )

    # 2. Entry that will be UPDATED
    e_update = memory_store.add_entry(
        subject="src/api.py",
        claim_text="API routing layer.",
        source_commit_sha="sha_api_v1",
    )

    # 3. Entry that will be DELETED
    e_delete = memory_store.add_entry(
        subject="src/removed.py",
        claim_text="Legacy handler to be dropped.",
        source_commit_sha="sha_removed",
    )

    author = AuthorRecord(id="lead@example.com", display_name="Lead")
    new_commit = CommitRecord(
        sha="sha_mixed_batch",
        author=author,
        timestamp=datetime.now(timezone.utc),
        message="chore: refactor API and drop legacy handler",
        modifications=[
            FileModificationRecord(path="src/api.py", change_type="M"),
            FileModificationRecord(path="src/removed.py", change_type="D"),
        ],
    )

    # 4. Entry that will be ADDED
    new_explanations = [
        {
            "subject": "src/new_feature.py",
            "claim_text": "Brand new feature pipeline.",
            "source_commit_sha": "sha_mixed_batch",
        }
    ]

    existing_files = {"src/stable.py", "src/api.py", "src/new_feature.py"}

    result = reconciler.reconcile(
        new_commits=[new_commit],
        existing_repo_files=existing_files,
        explanation_updater=lambda entry, commit: f"Updated: {entry.claim_text}",
        new_explanations=new_explanations,
    )

    assert result.no_oped == 1
    assert result.updated == 1
    assert result.deleted == 1
    assert result.added == 1
    assert result.total_processed == 4

    assert memory_store.get_entry(e_noop.id).last_action == ReconciliationAction.NO_OP
    assert memory_store.get_entry(e_update.id).last_action == ReconciliationAction.UPDATE
    assert memory_store.get_entry(e_delete.id).last_action == ReconciliationAction.DELETE
    assert memory_store.get_entry(e_delete.id).status == MemoryStatus.DELETED
