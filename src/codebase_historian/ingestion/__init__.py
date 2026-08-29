"""Ingestion module for git history, API clients, and AST parsing."""

from codebase_historian.ingestion.ast_parser import ASTParser
from codebase_historian.ingestion.git_extractor import GitExtractor
from codebase_historian.ingestion.models import (
    ASTClassRecord,
    ASTFunctionRecord,
    ASTImportRecord,
    AuthorRecord,
    CoChangeRecord,
    CommitRecord,
    FileModificationRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.pipeline import IngestionPipeline, IngestionResult

__all__ = [
    "ASTClassRecord",
    "ASTFunctionRecord",
    "ASTImportRecord",
    "ASTParser",
    "AuthorRecord",
    "CoChangeRecord",
    "CommitRecord",
    "FileModificationRecord",
    "FileStructureRecord",
    "GitExtractor",
    "IngestionPipeline",
    "IngestionResult",
]
