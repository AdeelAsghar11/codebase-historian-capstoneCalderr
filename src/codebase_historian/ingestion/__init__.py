"""Ingestion module for git history, API clients, and AST parsing."""

from codebase_historian.ingestion.models import (
    AuthorRecord,
    CommitRecord,
    FileModificationRecord,
    CoChangeRecord,
    ASTFunctionRecord,
    ASTClassRecord,
    ASTImportRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.git_extractor import GitExtractor
from codebase_historian.ingestion.ast_parser import ASTParser
from codebase_historian.ingestion.pipeline import IngestionPipeline, IngestionResult

__all__ = [
    "AuthorRecord",
    "CommitRecord",
    "FileModificationRecord",
    "CoChangeRecord",
    "ASTFunctionRecord",
    "ASTClassRecord",
    "ASTImportRecord",
    "FileStructureRecord",
    "GitExtractor",
    "ASTParser",
    "IngestionPipeline",
    "IngestionResult",
]
