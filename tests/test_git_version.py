from __future__ import annotations

from pathlib import Path
import subprocess
import warnings

import pytest

from texsmith.core import git_version


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    git_version.reset_cache()
    yield
    git_version.reset_cache()


def test_format_version_returns_free_form_string_unchanged() -> None:
    assert git_version.format_version("Draft 3") == "Draft 3"
    assert git_version.format_version("  consolidated v2  ") == "consolidated v2"


def test_format_version_ignores_empty_input() -> None:
    assert git_version.format_version("") == ""
    assert git_version.format_version(None) == ""
    assert git_version.format_version("   ") == ""


def test_format_version_resolves_git_keyword(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "tag", "v1.0.0")

    resolved = git_version.format_version("git", cwd=repo)
    assert resolved == "v1.0.0"


def test_format_version_marks_dirty_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "tag", "v0.1.0")
    (repo / "README.md").write_text("dirty", encoding="utf-8")

    assert git_version.format_version("git", cwd=repo) == "v0.1.0-dirty"


def test_format_version_falls_back_to_short_hash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")

    resolved = git_version.format_version("git", cwd=repo)
    assert resolved
    assert len(resolved) >= 7  # short hash, optionally with -dirty suffix


def test_format_version_without_repo_warns(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = git_version.format_version("git", cwd=not_a_repo)
    assert result == ""
    assert any("no git repository" in str(w.message) for w in captured)


def test_format_version_keyword_is_case_insensitive(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "tag", "v2.0")

    assert git_version.format_version("Git", cwd=repo) == "v2.0"
    assert git_version.format_version("GIT", cwd=repo) == "v2.0"
