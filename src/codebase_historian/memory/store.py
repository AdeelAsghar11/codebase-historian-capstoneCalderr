"""
SQLite persistent storage for reconciled memory, audit logs, and index state.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from codebase_historian.memory.models import (
    AuditLogEntry,
    IndexState,
    MemoryEntry,
    MemoryStatus,
    ReconciliationAction,
)


class SQLiteMemoryStore:
    """Relational database store managing memory entries, audit logs, and index state."""

    def __init__(self, db_path: str = "historian.db"):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        """Create database tables per DATA_MODEL.md specification."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                source_commit_sha TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                last_validated_at TIMESTAMP NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'stale', 'deleted')),
                last_action TEXT NOT NULL CHECK (last_action IN ('add', 'update', 'delete', 'no-op'))
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                caller_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                status_code INTEGER NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS index_state (
                repo_url TEXT PRIMARY KEY,
                last_indexed_commit_sha TEXT NOT NULL,
                last_indexed_at TIMESTAMP NOT NULL
            );
            """
        )
        self.conn.commit()

    # --- Memory Entry Operations ---

    def add_entry(
        self,
        subject: str,
        claim_text: str,
        source_commit_sha: str,
        entry_id: str | None = None,
    ) -> MemoryEntry:
        """Create and store a new active memory entry."""
        now = datetime.now(UTC)
        eid = entry_id or str(uuid4())
        entry = MemoryEntry(
            id=eid,
            subject=subject,
            claim_text=claim_text,
            source_commit_sha=source_commit_sha,
            created_at=now,
            last_validated_at=now,
            status=MemoryStatus.ACTIVE,
            last_action=ReconciliationAction.ADD,
        )
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_entries (id, subject, claim_text, source_commit_sha, created_at, last_validated_at, status, last_action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.subject,
                entry.claim_text,
                entry.source_commit_sha,
                entry.created_at.isoformat(),
                entry.last_validated_at.isoformat(),
                entry.status.value,
                entry.last_action.value,
            ),
        )
        self.conn.commit()
        return entry

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        """Fetch a memory entry by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        return self._row_to_entry(row) if row else None

    def get_by_subject(
        self, subject: str, status: MemoryStatus | None = None
    ) -> list[MemoryEntry]:
        """Fetch all entries matching a subject."""
        cursor = self.conn.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM memory_entries WHERE subject = ? AND status = ?",
                (subject, status.value),
            )
        else:
            cursor.execute(
                "SELECT * FROM memory_entries WHERE subject = ?", (subject,)
            )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def list_entries(
        self, status: MemoryStatus | None = None
    ) -> list[MemoryEntry]:
        """List all entries, optionally filtered by status."""
        cursor = self.conn.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM memory_entries WHERE status = ? ORDER BY created_at DESC",
                (status.value,),
            )
        else:
            cursor.execute("SELECT * FROM memory_entries ORDER BY created_at DESC")
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def update_entry(
        self,
        entry_id: str,
        claim_text: str | None = None,
        source_commit_sha: str | None = None,
        status: MemoryStatus | None = None,
        last_action: ReconciliationAction | None = None,
        last_validated_at: datetime | None = None,
    ) -> MemoryEntry | None:
        """Update an existing memory entry."""
        current = self.get_entry(entry_id)
        if not current:
            return None

        new_claim = claim_text if claim_text is not None else current.claim_text
        new_sha = (
            source_commit_sha
            if source_commit_sha is not None
            else current.source_commit_sha
        )
        new_status = status if status is not None else current.status
        new_action = last_action if last_action is not None else current.last_action
        new_val_time = last_validated_at or datetime.now(UTC)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE memory_entries
            SET claim_text = ?, source_commit_sha = ?, status = ?, last_action = ?, last_validated_at = ?
            WHERE id = ?
            """,
            (
                new_claim,
                new_sha,
                new_status.value,
                new_action.value,
                new_val_time.isoformat(),
                entry_id,
            ),
        )
        self.conn.commit()
        return self.get_entry(entry_id)

    # --- Index State Operations ---

    def get_index_state(self, repo_url: str) -> IndexState | None:
        """Retrieve repository indexing state."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM index_state WHERE repo_url = ?", (repo_url,))
        row = cursor.fetchone()
        if not row:
            return None
        return IndexState(
            repo_url=row["repo_url"],
            last_indexed_commit_sha=row["last_indexed_commit_sha"],
            last_indexed_at=datetime.fromisoformat(row["last_indexed_at"]),
        )

    def set_index_state(self, repo_url: str, last_commit_sha: str) -> IndexState:
        """Update or insert repository indexing state."""
        now = datetime.now(UTC)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO index_state (repo_url, last_indexed_commit_sha, last_indexed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(repo_url) DO UPDATE SET
                last_indexed_commit_sha = excluded.last_indexed_commit_sha,
                last_indexed_at = excluded.last_indexed_at
            """,
            (repo_url, last_commit_sha, now.isoformat()),
        )
        self.conn.commit()
        return IndexState(
            repo_url=repo_url,
            last_indexed_commit_sha=last_commit_sha,
            last_indexed_at=now,
        )

    # --- Audit Log Operations ---

    def log_audit(
        self,
        caller_id: str,
        tool_name: str,
        endpoint: str,
        latency_ms: int,
        status_code: int,
    ) -> int:
        """Record an API/tool call into the audit log."""
        now = datetime.now(UTC)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_log (timestamp, caller_id, tool_name, endpoint, latency_ms, status_code)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                now.isoformat(),
                caller_id,
                tool_name,
                endpoint,
                latency_ms,
                status_code,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_audit_logs(self, limit: int = 100) -> list[AuditLogEntry]:
        """Fetch audit log entries."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [
            AuditLogEntry(
                id=row["id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                caller_id=row["caller_id"],
                tool_name=row["tool_name"],
                endpoint=row["endpoint"],
                latency_ms=row["latency_ms"],
                status_code=row["status_code"],
            )
            for row in cursor.fetchall()
        ]

    get_audit_logs = list_audit_logs

    def close(self) -> None:
        self.conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            subject=row["subject"],
            claim_text=row["claim_text"],
            source_commit_sha=row["source_commit_sha"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_validated_at=datetime.fromisoformat(row["last_validated_at"]),
            status=MemoryStatus(row["status"]),
            last_action=ReconciliationAction(row["last_action"]),
        )
