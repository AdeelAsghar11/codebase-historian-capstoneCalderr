"""
GitHub repository target resolver.
Detects GitHub URLs or owner/repo shorthands and clones/updates repositories locally
using the GitHub CLI (`gh`) when available, with graceful GitPython fallback.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Tuple

import git
from github import Github


def get_active_github_token() -> str | None:
    """Detect active GitHub token from environment variables or GitHub CLI (`gh auth token`)."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and token.strip():
        return token.strip()

    gh_path = shutil.which("gh")
    if gh_path:
        try:
            res = subprocess.run(
                [gh_path, "auth", "token"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return None


def list_github_user_repos(
    token: str | None = None,
    username: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    List repositories accessible to the user on github.com.
    Prioritizes:
    1. Authenticated PyGithub user repositories (if token or active gh session exists)
    2. GitHub CLI `gh repo list`
    3. Public user repositories by username
    """
    active_token = token or get_active_github_token()
    repos_list = []

    # Strategy 1: PyGithub with authentication token
    if active_token:
        try:
            g = Github(active_token)
            user = g.get_user()
            for r in user.get_repos(sort="updated"):
                if len(repos_list) >= limit:
                    break
                repos_list.append(
                    {
                        "full_name": r.full_name,
                        "name": r.name,
                        "description": r.description or "No description",
                        "private": r.private,
                        "stars": r.stargazers_count,
                        "url": r.html_url,
                        "default_branch": r.default_branch or "main",
                    }
                )
            if repos_list:
                return repos_list
        except Exception:
            pass

    # Strategy 2: GitHub CLI `gh repo list`
    gh_path = shutil.which("gh")
    if gh_path:
        try:
            cmd = [
                gh_path,
                "repo",
                "list",
                "--json",
                "nameWithOwner,name,description,isPrivate,stargazerCount,url",
                "--limit",
                str(limit),
            ]
            if username:
                cmd.insert(3, username)
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                for item in data:
                    repos_list.append(
                        {
                            "full_name": item.get("nameWithOwner"),
                            "name": item.get("name"),
                            "description": item.get("description") or "No description",
                            "private": item.get("isPrivate", False),
                            "stars": item.get("stargazerCount", 0),
                            "url": item.get("url"),
                            "default_branch": "main",
                        }
                    )
                if repos_list:
                    return repos_list
        except Exception:
            pass

    # Strategy 3: Unauthenticated PyGithub by public username
    if username:
        try:
            g = Github()
            user = g.get_user(username)
            for r in user.get_repos(sort="updated"):
                if len(repos_list) >= limit:
                    break
                repos_list.append(
                    {
                        "full_name": r.full_name,
                        "name": r.name,
                        "description": r.description or "No description",
                        "private": False,
                        "stars": r.stargazers_count,
                        "url": r.html_url,
                        "default_branch": r.default_branch or "main",
                    }
                )
            return repos_list
        except Exception:
            pass

    return repos_list


def is_github_target(target: str) -> bool:
    """
    Check if a target string represents a remote GitHub repository.
    Recognizes:
    - https://github.com/owner/repo[.git]
    - http://github.com/owner/repo[.git]
    - git@github.com:owner/repo[.git]
    - owner/repo shorthand (when not an existing local directory)
    """
    clean = target.strip()
    if not clean:
        return False

    # Check for full GitHub URLs
    if "github.com/" in clean or clean.startswith("git@github.com:"):
        return True

    # If it already exists on the local filesystem, treat as local path
    if Path(clean).exists():
        return False

    # Check for owner/repo pattern (e.g. 'pallets/flask', 'octocat/Hello-World')
    shorthand_pattern = r"^[\w.-]+/[\w.-]+$"
    if re.match(shorthand_pattern, clean) and not (clean.startswith("./") or clean.startswith(".\\")):
        return True

    return False


def normalize_github_target(target: str) -> Tuple[str, str, str]:
    """
    Extract (owner, repo_name, clone_url) from a GitHub target string.
    """
    clean = target.strip()
    clean = re.sub(r"\.git$", "", clean)

    if clean.startswith("git@github.com:"):
        path_part = clean.split("git@github.com:", 1)[1]
    elif "github.com/" in clean:
        path_part = clean.split("github.com/", 1)[1]
    else:
        path_part = clean

    parts = [p for p in path_part.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub repository format: '{target}'. Expected 'owner/repo' or GitHub URL.")

    owner, repo_name = parts[0], parts[1]
    clone_url = f"https://github.com/{owner}/{repo_name}.git"
    return owner, repo_name, clone_url


def clone_github_repo(
    target: str,
    dest_dir: str | Path | None = None,
    prefer_gh_cli: bool = True,
) -> Tuple[Path, str]:
    """
    Clone or update a remote GitHub repository into a local cache directory.
    Prefers GitHub CLI (`gh repo clone`) if installed, with GitPython fallback.
    Returns (cloned_path, method_used).
    """
    owner, repo_name, clone_url = normalize_github_target(target)

    if dest_dir is not None:
        target_dir = Path(dest_dir).resolve()
    else:
        # Default local cache under .repos/
        target_dir = (Path(".repos") / f"{owner}_{repo_name}").resolve()

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # If repo already exists locally and has .git, pull latest or reuse
    if (target_dir / ".git").exists():
        try:
            repo = git.Repo(target_dir)
            if repo.remotes:
                repo.remotes.origin.pull()
        except Exception:
            # If offline or pull fails, proceed with existing local clone
            pass
        return target_dir, "cached"

    # Strategy 1: Attempt clone using GitHub CLI (`gh repo clone`) if available
    gh_path = shutil.which("gh")
    if prefer_gh_cli and gh_path:
        try:
            cmd = [gh_path, "repo", "clone", f"{owner}/{repo_name}", str(target_dir)]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if res.returncode == 0 and (target_dir / ".git").exists():
                return target_dir, "gh_cli"
        except Exception:
            pass

    # Strategy 2: Fall back to GitPython / standard git clone
    try:
        git.Repo.clone_from(clone_url, str(target_dir))
        return target_dir, "git_clone"
    except Exception as e:
        raise RuntimeError(
            f"Failed to clone GitHub repository '{owner}/{repo_name}' from {clone_url}: {e}"
        ) from e


def resolve_repo_target(target: str, dest_dir: str | Path | None = None) -> Tuple[Path, bool]:
    """
    Resolve a repository target string to a local directory Path.
    Returns (resolved_path, was_github_cloned).
    """
    if is_github_target(target):
        path, _ = clone_github_repo(target, dest_dir=dest_dir)
        return path, True

    return Path(target).resolve(), False
