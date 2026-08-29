"""
Reconciliation engine for memory entries.
Implements the add / update / delete / no-op state machine specified in DATA_MODEL.md.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from codebase_historian.ingestion.models import CommitRecord
from codebase_historian.memory.models import (
    MemoryEntry,
    MemoryStatus,
    ReconciliationAction,
)
from codebase_historian.memory.store import SQLiteMemoryStore


class ReconciliationResult(BaseModel):
    total_processed: int = 0
    added: int = 0
    updated: int = 0
    deleted: int = 0
    no_oped: int = 0
    entries: list[MemoryEntry] = Field(default_factory=list)


class MemoryReconciler:
    """Executes reconciliation passes against the memory store on new commit ingestion."""

    def __init__(self, store: SQLiteMemoryStore):
        self.store = store

    def reconcile(
        self,
        new_commits: list[CommitRecord],
        existing_repo_files: set[str],
        explanation_updater: Callable[[MemoryEntry, CommitRecord], str | None] | None = None,
        new_explanations: list[dict[str, str]] | None = None,
    ) -> ReconciliationResult:
        """
        Execute a reconciliation pass on all memory entries.

        State transitions:
        - DELETE: Subject deleted from repository or removed by commit.
        - UPDATE: Subject touched by new commit; regenerate/update claim or mark stale.
        - NO-OP:  Subject untouched; update last_validated_at timestamp.
        - ADD:    New subject explanation supplied.
        """
        result = ReconciliationResult()
        now = datetime.now(UTC)

        # 1. Map changes from new commits
        touched_files: dict[str, CommitRecord] = {}
        deleted_files: set[str] = set()

        for commit in new_commits:
            for mod in commit.modifications:
                clean_path = mod.path.replace("\\", "/")
                if mod.change_type == "D":
                    deleted_files.add(clean_path)
                else:
                    touched_files[clean_path] = commit
                    if clean_path in deleted_files:
                        deleted_files.remove(clean_path)

        # Normalize existing file paths
        normalized_existing_files = {p.replace("\\", "/") for p in existing_repo_files}

        # 2. Reconcile existing non-deleted entries
        existing_entries = self.store.list_entries()
        for entry in existing_entries:
            if entry.status == MemoryStatus.DELETED:
                continue

            result.total_processed += 1
            subject_clean = entry.subject.replace("\\", "/")
            file_base = subject_clean.split(":")[0]  # In case subject is "file:symbol"

            # Check for DELETION
            is_deleted = (
                file_base in deleted_files
                or (normalized_existing_files and file_base not in normalized_existing_files)
            )

            if is_deleted:
                updated = self.store.update_entry(
                    entry_id=entry.id,
                    status=MemoryStatus.DELETED,
                    last_action=ReconciliationAction.DELETE,
                    last_validated_at=now,
                )
                if updated:
                    result.deleted += 1
                    result.entries.append(updated)
                continue

            # Check for UPDATE (subject was touched by a commit since last validation)
            latest_commit = touched_files.get(file_base)
            if latest_commit:
                new_claim = None
                new_status = MemoryStatus.STALE
                if explanation_updater:
                    new_claim = explanation_updater(entry, latest_commit)
                    if new_claim:
                        new_status = MemoryStatus.ACTIVE

                updated = self.store.update_entry(
                    entry_id=entry.id,
                    claim_text=new_claim if new_claim else entry.claim_text,
                    source_commit_sha=latest_commit.sha,
                    status=new_status,
                    last_action=ReconciliationAction.UPDATE,
                    last_validated_at=now,
                )
                if updated:
                    result.updated += 1
                    result.entries.append(updated)
                continue

            # Subject untouched -> NO-OP
            updated = self.store.update_entry(
                entry_id=entry.id,
                status=entry.status,
                last_action=ReconciliationAction.NO_OP,
                last_validated_at=now,
            )
            if updated:
                result.no_oped += 1
                result.entries.append(updated)

        # 3. Process new ADD entries
        if new_explanations:
            for item in new_explanations:
                subj = item["subject"]
                claim = item["claim_text"]
                sha = item.get("source_commit_sha", "unknown")
                created = self.store.add_entry(
                    subject=subj,
                    claim_text=claim,
                    source_commit_sha=sha,
                )
                result.total_processed += 1
                result.added += 1
                result.entries.append(created)

        return result
