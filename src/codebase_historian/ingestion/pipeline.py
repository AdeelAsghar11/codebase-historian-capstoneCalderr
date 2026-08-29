"""
Ingestion pipeline orchestrator.
Coordinates git history extraction, co-change computation, and AST parsing across repository files.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from codebase_historian.ingestion.models import (
    CommitRecord,
    CoChangeRecord,
    FileStructureRecord,
)
from codebase_historian.ingestion.git_extractor import GitExtractor
from codebase_historian.ingestion.ast_parser import ASTParser


class IngestionResult(BaseModel):
    repo_path: str
    last_indexed_commit_sha: Optional[str] = None
    commits: List[CommitRecord] = Field(default_factory=list)
    co_changes: List[CoChangeRecord] = Field(default_factory=list)
    file_structures: List[FileStructureRecord] = Field(default_factory=list)
    dependencies: List[Tuple[str, str, str]] = Field(default_factory=list)  # (source, target, kind)
    stats: Dict[str, int] = Field(default_factory=dict)


class IngestionPipeline:
    """Ingests a git repository's commit history and AST structure."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.git_extractor = GitExtractor(self.repo_path)
        self.ast_parser = ASTParser()

    def run(
        self,
        branch: Optional[str] = None,
        max_commits: Optional[int] = None,
        since_sha: Optional[str] = None,
    ) -> IngestionResult:
        """Execute full or incremental ingestion on the repository."""
        # 1. Extract git commits and modifications
        commits = self.git_extractor.extract_commits(
            branch=branch,
            max_count=max_commits,
            since_sha=since_sha,
        )

        # 2. Compute co-changes across commits
        co_changes = self.git_extractor.compute_co_changes(commits)

        # 3. Parse AST for all Python files in the repository
        file_structures: List[FileStructureRecord] = []
        for py_file in self.repo_path.rglob("*.py"):
            # Skip virtual environments and hidden dirs
            rel_path = py_file.relative_to(self.repo_path).as_posix()
            if rel_path.startswith((".venv", "venv", ".git", "build", "dist")):
                continue
            structure = self.ast_parser.parse_file(py_file)
            if structure:
                structure.path = rel_path
                file_structures.append(structure)

        # 4. Resolve static DEPENDS_ON import dependencies
        dependencies = self.ast_parser.resolve_dependencies(file_structures, self.repo_path)

        last_sha = commits[-1].sha if commits else None

        stats = {
            "total_commits": len(commits),
            "total_co_change_pairs": len(co_changes),
            "total_python_files": len(file_structures),
            "total_dependencies": len(dependencies),
        }

        return IngestionResult(
            repo_path=str(self.repo_path),
            last_indexed_commit_sha=last_sha,
            commits=commits,
            co_changes=co_changes,
            file_structures=file_structures,
            dependencies=dependencies,
            stats=stats,
        )
