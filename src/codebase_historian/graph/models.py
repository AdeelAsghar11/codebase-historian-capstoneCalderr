"""
Data types and schemas for the Knowledge Graph.
"""

from enum import Enum

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
    first_seen_commit: str | None = None
    last_modified_commit: str | None = None
    centrality: float = 0.0


class CommitNodeData(BaseModel):
    sha: str
    author_id: str
    timestamp: str
    message: str
    parent_shas: list[str] = Field(default_factory=list)


class PullRequestNodeData(BaseModel):
    number: int
    title: str
    description: str | None = None
    author: str
    merged_at: str | None = None
    status: str = "merged"


class IssueNodeData(BaseModel):
    number: int
    title: str
    body: str | None = None
    author: str
    closed_at: str | None = None
    status: str = "closed"


class AuthorNodeData(BaseModel):
    id: str
    display_name: str


class ModifiesEdgeData(BaseModel):
    lines_added: int = 0
    lines_removed: int = 0
    diff_summary: str | None = None


class CoChangesWithEdgeData(BaseModel):
    co_change_count: int = 1
    last_co_change_commit: str


class DependsOnEdgeData(BaseModel):
    import_kind: str = "direct"  # direct, from, relative
