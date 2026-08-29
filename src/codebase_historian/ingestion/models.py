"""
Pydantic data models for the ingestion layer.
Represents raw extracted entities from git history, AST parsing, and issue/PR sources.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AuthorRecord(BaseModel):
    id: str  # Email or unique platform ID
    display_name: str


class FileModificationRecord(BaseModel):
    path: str
    change_type: str  # 'A' (added), 'M' (modified), 'D' (deleted), 'R' (renamed)
    lines_added: int = 0
    lines_removed: int = 0
    diff_summary: str | None = None


class CommitRecord(BaseModel):
    sha: str
    author: AuthorRecord
    timestamp: datetime
    message: str
    parent_shas: list[str] = Field(default_factory=list)
    modifications: list[FileModificationRecord] = Field(default_factory=list)


class CoChangeRecord(BaseModel):
    file_a: str
    file_b: str
    co_change_count: int = 1
    last_co_change_commit: str


class ASTFunctionRecord(BaseModel):
    name: str
    qualname: str
    docstring: str | None = None
    start_line: int
    end_line: int
    is_async: bool = False


class ASTClassRecord(BaseModel):
    name: str
    qualname: str
    docstring: str | None = None
    start_line: int
    end_line: int
    methods: list[ASTFunctionRecord] = Field(default_factory=list)
    base_classes: list[str] = Field(default_factory=list)


class ASTImportRecord(BaseModel):
    module: str | None = None  # from module import ... or import module
    names: list[str] = Field(default_factory=list)
    alias_map: dict[str, str] = Field(default_factory=dict)
    import_kind: str = "direct"  # "direct", "from", "relative"
    level: int = 0  # 0 for absolute, 1 for '.', 2 for '..', etc.


class FileStructureRecord(BaseModel):
    path: str
    language: str = "python"
    classes: list[ASTClassRecord] = Field(default_factory=list)
    functions: list[ASTFunctionRecord] = Field(default_factory=list)
    imports: list[ASTImportRecord] = Field(default_factory=list)
    docstring: str | None = None
    raw_content: str | None = None
