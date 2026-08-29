"""
Data types and schemas for the Knowledge Graph.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    FILE = "File"
    COMMIT = "Commit"
    PULL_REQUEST = "PullRequest"
    ISSUE = "Issue"
    AUTHOR = "Author"


class EdgeType(str, Enum):
    MODIFIES = "MODIFIES"
    AUTHORED_BY = "AUTHORED_BY"
    INCLUDES = "INCLUDES"
    REFERENCES = "REFERENCES"
    CO_CHANGES_WITH = "CO_CHANGES_WITH"
    DEPENDS_ON = "DEPENDS_ON"


class FileNodeData(BaseModel):
    path: str
    language: str = "python"
    first_seen_commit: Optional[str] = None
    last_modified_commit: Optional[str] = None
    centrality: float = 0.0


class CommitNodeData(BaseModel):
    sha: str
    author_id: str
    timestamp: str
    message: str
    parent_shas: List[str] = Field(default_factory=list)


class PullRequestNodeData(BaseModel):
    number: int
    title: str
    description: Optional[str] = None
    author: str
    merged_at: Optional[str] = None
    status: str = "merged"


class IssueNodeData(BaseModel):
    number: int
    title: str
    body: Optional[str] = None
    author: str
    closed_at: Optional[str] = None
    status: str = "closed"


class AuthorNodeData(BaseModel):
    id: str
    display_name: str


class ModifiesEdgeData(BaseModel):
    lines_added: int = 0
    lines_removed: int = 0
    diff_summary: Optional[str] = None


class CoChangesWithEdgeData(BaseModel):
    co_change_count: int = 1
    last_co_change_commit: str


class DependsOnEdgeData(BaseModel):
    import_kind: str = "direct"  # direct, from, relative
