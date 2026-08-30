"""Ingestion module for git history, API clients, and AST parsing."""

from codebase_historian.ingestion.ast_parser import ASTParser
from codebase_historian.ingestion.git_extractor import GitExtractor
from codebase_historian.ingestion.github_resolver import (
    clone_github_repo,
    get_active_github_token,
    is_github_target,
    list_github_user_repos,
    normalize_github_target,
    resolve_repo_target,
)
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
    "clone_github_repo",
    "get_active_github_token",
    "is_github_target",
    "list_github_user_repos",
    "normalize_github_target",
    "resolve_repo_target",
]
