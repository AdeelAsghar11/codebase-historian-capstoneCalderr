"""
Git history extraction using GitPython.
Extracts commits, author metadata, file modifications, diff statistics, and co-change frequencies.
"""

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import git

from codebase_historian.ingestion.models import (
    AuthorRecord,
    CoChangeRecord,
    CommitRecord,
    FileModificationRecord,
)


class GitExtractor:
    """Extracts git commit history and file co-change metrics from a local repository."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.repo = git.Repo(self.repo_path)

    def extract_commits(
        self,
        branch: str | None = None,
        max_count: int | None = None,
        since_sha: str | None = None,
        since_commit: str | None = None,
    ) -> list[CommitRecord]:
        """
        Extract commit records from the repository.
        If `since_sha` or `since_commit` is provided, only commits after that SHA are extracted.
        """
        target_since = since_sha or since_commit
        rev_range = branch if branch else "HEAD"
        if target_since:
            rev_range = f"{target_since}..{rev_range}"

        try:
            commits_iterable = list(self.repo.iter_commits(rev_range, max_count=max_count))
        except git.GitCommandError:
            # If repo is empty or rev_range invalid
            return []

        # Process commits in topological order (oldest to newest for incremental consistency)
        commits_iterable.reverse()

        records: list[CommitRecord] = []
        for commit in commits_iterable:
            author_record = AuthorRecord(
                id=commit.author.email or commit.author.name or "unknown",
                display_name=commit.author.name or "Unknown",
            )
            timestamp = datetime.fromtimestamp(commit.authored_date, tz=UTC)
            parent_shas = [p.hexsha for p in commit.parents]

            modifications = self._extract_modifications(commit)

            records.append(
                CommitRecord(
                    sha=commit.hexsha,
                    author=author_record,
                    timestamp=timestamp,
                    message=commit.message.strip(),
                    parent_shas=parent_shas,
                    modifications=modifications,
                )
            )
        return records

    def _extract_modifications(self, commit: git.Commit) -> list[FileModificationRecord]:
        """Extract file-level changes and diff stats for a given commit."""
        modifications: list[FileModificationRecord] = []

        try:
            stats = commit.stats.files
        except Exception:
            stats = {}

        if not commit.parents:
            # Initial root commit - diff against empty tree
            try:
                diffs = commit.diff(git.NULL_TREE)
                for diff in diffs:
                    path = diff.b_path or diff.a_path
                    if not path:
                        continue
                    file_stat = stats.get(path, {"insertions": 0, "deletions": 0})
                    modifications.append(
                        FileModificationRecord(
                            path=path.replace("\\", "/"),
                            change_type="A",
                            lines_added=file_stat.get("insertions", 0),
                            lines_removed=file_stat.get("deletions", 0),
                            diff_summary=f"Added file in initial commit ({file_stat.get('insertions', 0)} lines)",
                        )
                    )
            except Exception:
                pass
        else:
            # Diff against primary parent
            primary_parent = commit.parents[0]
            try:
                diffs = primary_parent.diff(commit)
                for diff in diffs:
                    change_type = diff.change_type or "M"
                    path = diff.b_path or diff.a_path
                    if not path:
                        continue
                    clean_path = path.replace("\\", "/")
                    file_stat = stats.get(path, stats.get(clean_path, {"insertions": 0, "deletions": 0}))

                    summary_parts = []
                    if diff.renamed_file:
                        summary_parts.append(f"Renamed from {diff.a_path} to {diff.b_path}")
                    elif change_type == "A":
                        summary_parts.append("File added")
                    elif change_type == "D":
                        summary_parts.append("File deleted")
                    else:
                        summary_parts.append("File modified")

                    ins = file_stat.get("insertions", 0)
                    dels = file_stat.get("deletions", 0)
                    summary_parts.append(f"+{ins}/-{dels}")

                    modifications.append(
                        FileModificationRecord(
                            path=clean_path,
                            change_type=change_type,
                            lines_added=ins,
                            lines_removed=dels,
                            diff_summary=", ".join(summary_parts),
                        )
                    )
            except Exception:
                pass

        return modifications

    def compute_co_changes(self, commits: list[CommitRecord]) -> list[CoChangeRecord]:
        """
        Compute co-change frequencies across all commits.
        Pairs are sorted alphabetically (file_a < file_b) for a canonical key.
        """
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        last_commit: dict[tuple[str, str], str] = {}

        for commit in commits:
            # Only consider modified or added files (ignore deletions in co-change coupling)
            touched_files = sorted(
                list(
                    {
                        mod.path
                        for mod in commit.modifications
                        if mod.change_type in ("A", "M", "R")
                    }
                )
            )

            for i in range(len(touched_files)):
                for j in range(i + 1, len(touched_files)):
                    pair = (touched_files[i], touched_files[j])
                    pair_counts[pair] += 1
                    last_commit[pair] = commit.sha

        co_change_records: list[CoChangeRecord] = []
        for (file_a, file_b), count in pair_counts.items():
            co_change_records.append(
                CoChangeRecord(
                    file_a=file_a,
                    file_b=file_b,
                    co_change_count=count,
                    last_co_change_commit=last_commit[(file_a, file_b)],
                )
            )

        return co_change_records
