"""
Pydantic data models for the ingestion layer.
Represents raw extracted entities from git history, AST parsing, and issue/PR sources.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AuthorRecord(BaseModel):
    id: str  # Email or unique platform ID
    display_name: str


class FileModificationRecord(BaseModel):
    path: str
    change_type: str  # 'A' (added), 'M' (modified), 'D' (deleted), 'R' (renamed)
    lines_added: int = 0
    lines_removed: int = 0
    diff_summary: Optional[str] = None


class CommitRecord(BaseModel):
    sha: str
    author: AuthorRecord
    timestamp: datetime
    message: str
    parent_shas: List[str] = Field(default_factory=list)
    modifications: List[FileModificationRecord] = Field(default_factory=list)


class CoChangeRecord(BaseModel):
    file_a: str
    file_b: str
    co_change_count: int = 1
    last_co_change_commit: str


class ASTFunctionRecord(BaseModel):
    name: str
    qualname: str
    docstring: Optional[str] = None
    start_line: int
    end_line: int
    is_async: bool = False


class ASTClassRecord(BaseModel):
    name: str
    qualname: str
    docstring: Optional[str] = None
    start_line: int
    end_line: int
    methods: List[ASTFunctionRecord] = Field(default_factory=list)
    base_classes: List[str] = Field(default_factory=list)


class ASTImportRecord(BaseModel):
    module: Optional[str] = None  # from module import ... or import module
    names: List[str] = Field(default_factory=list)
    alias_map: Dict[str, str] = Field(default_factory=dict)
    import_kind: str = "direct"  # "direct", "from", "relative"
    level: int = 0  # 0 for absolute, 1 for '.', 2 for '..', etc.


class FileStructureRecord(BaseModel):
    path: str
    language: str = "python"
    classes: List[ASTClassRecord] = Field(default_factory=list)
    functions: List[ASTFunctionRecord] = Field(default_factory=list)
    imports: List[ASTImportRecord] = Field(default_factory=list)
    docstring: Optional[str] = None
    raw_content: Optional[str] = None
