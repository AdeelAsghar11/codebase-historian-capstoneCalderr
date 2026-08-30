"""
Unit tests for the GitHub repository target resolver and remote clone utilities.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codebase_historian.ingestion.github_resolver import (
    clone_github_repo,
    get_active_github_token,
    is_github_target,
    list_github_user_repos,
    normalize_github_target,
    resolve_repo_target,
)


def test_is_github_target():
    assert is_github_target("https://github.com/pallets/flask") is True
    assert is_github_target("http://github.com/pallets/flask.git") is True
    assert is_github_target("git@github.com:pallets/flask.git") is True
    assert is_github_target("pallets/flask") is True
    assert is_github_target("octocat/Hello-World") is True

    # Local path checks
    assert is_github_target(".") is False
    assert is_github_target("./src") is False
    assert is_github_target("nonexistent_single_word") is False
    assert is_github_target("") is False


def test_normalize_github_target():
    owner, repo, clone_url = normalize_github_target("pallets/flask")
    assert owner == "pallets"
    assert repo == "flask"
    assert clone_url == "https://github.com/pallets/flask.git"

    owner2, repo2, clone_url2 = normalize_github_target("https://github.com/octocat/Hello-World.git")
    assert owner2 == "octocat"
    assert repo2 == "Hello-World"
    assert clone_url2 == "https://github.com/octocat/Hello-World.git"

    owner3, repo3, clone_url3 = normalize_github_target("git@github.com:owner/repo.git")
    assert owner3 == "owner"
    assert repo3 == "repo"
    assert clone_url3 == "https://github.com/owner/repo.git"

    with pytest.raises(ValueError):
        normalize_github_target("invalid_repo_name")


def test_resolve_repo_target_local():
    local_path = Path(".").resolve()
    resolved, was_github = resolve_repo_target(".")
    assert was_github is False
    assert resolved == local_path


@patch("codebase_historian.ingestion.github_resolver.Github")
def test_list_github_user_repos_mock(mock_github_cls):
    mock_repo = MagicMock()
    mock_repo.full_name = "testuser/my-repo"
    mock_repo.name = "my-repo"
    mock_repo.description = "A sample test repo"
    mock_repo.private = False
    mock_repo.stargazers_count = 12
    mock_repo.html_url = "https://github.com/testuser/my-repo"
    mock_repo.default_branch = "main"

    mock_user = MagicMock()
    mock_user.get_repos.return_value = [mock_repo]

    mock_instance = MagicMock()
    mock_instance.get_user.return_value = mock_user
    mock_github_cls.return_value = mock_instance

    repos = list_github_user_repos(token="fake_token_123")
    assert len(repos) == 1
    assert repos[0]["full_name"] == "testuser/my-repo"
    assert repos[0]["private"] is False
    assert repos[0]["stars"] == 12


def test_get_active_github_token_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "mock_gh_token_abc")
    token = get_active_github_token()
    assert token == "mock_gh_token_abc"


@patch("codebase_historian.ingestion.github_resolver.git.Repo.clone_from")
def test_clone_github_repo_mock(mock_clone, tmp_path):
    dest_dir = tmp_path / "mock_clone_dir"
    target = "pallets/flask"

    # Simulate clone creating directory
    def side_effect(url, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        return MagicMock()

    mock_clone.side_effect = side_effect

    cloned_path, method = clone_github_repo(target, dest_dir=dest_dir, prefer_gh_cli=False)
    assert cloned_path == dest_dir.resolve()
    assert method == "git_clone"
    mock_clone.assert_called_once()
