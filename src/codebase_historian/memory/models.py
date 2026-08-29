"""
Data models for the SQLite memory store, audit logs, and reconciliation logic.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    DELETED = "deleted"


class ReconciliationAction(str, Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    NO_OP = "no-op"


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    subject: str
    claim_text: str
    source_commit_sha: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_validated_at: datetime = Field(default_factory=datetime.utcnow)
    status: MemoryStatus = MemoryStatus.ACTIVE
    last_action: ReconciliationAction = ReconciliationAction.ADD


class IndexState(BaseModel):
    repo_url: str
    last_indexed_commit_sha: str
    last_indexed_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLogEntry(BaseModel):
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    caller_id: str
    tool_name: str
    endpoint: str
    latency_ms: int
    status_code: int
