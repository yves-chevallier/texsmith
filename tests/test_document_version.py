from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from texsmith.core import git_version
from texsmith.core.document_version import (
    DocumentVersionError,
    FreeFormVersion,
    GitVersion,
    SemverDictVersion,
    SemverListVersion,
    format_version,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture(autouse=True)
def _clear_cache():
    git_version.reset_cache()
    yield
    git_version.reset_cache()


@pytest.fixture
def repo_with_tag(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("hello", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "tag", "v1.0.0")
    return repo


# --- Free-form text -----------------------------------------------------------


def test_format_version_returns_free_form_string_unchanged() -> None:
    assert format_version("Draft 3") == "Draft 3"
    assert format_version("  consolidated v2  ") == "consolidated v2"


def test_format_version_ignores_empty_input() -> None:
    assert format_version("") == ""
    assert format_version(None) == ""
    assert format_version("   ") == ""


# --- Legacy ``git`` keyword (backward compat) --------------------------------


def test_format_version_resolves_git_keyword(repo_with_tag: Path) -> None:
    assert format_version("git", cwd=repo_with_tag) == "v1.0.0"


def test_format_version_keyword_is_case_insensitive(repo_with_tag: Path) -> None:
    assert format_version("Git", cwd=repo_with_tag) == "v1.0.0"
    assert format_version("GIT", cwd=repo_with_tag) == "v1.0.0"


# --- Semver list shape --------------------------------------------------------


def test_semver_list_renders_dotted_string() -> None:
    assert format_version([2, 3, 0]) == "2.3.0"
    assert format_version([2, 3]) == "2.3"
    assert format_version([2]) == "2"


def test_semver_list_rejects_non_integer_parts() -> None:
    with pytest.raises(DocumentVersionError):
        format_version([2, "3", 0])
    with pytest.raises(DocumentVersionError):
        format_version([2, -1])


def test_semver_list_rejects_empty_list() -> None:
    with pytest.raises(DocumentVersionError):
        format_version([])


# --- Semver dict shape --------------------------------------------------------


def test_semver_dict_renders_canonical_form() -> None:
    assert format_version({"major": 2, "minor": 3, "patch": 0}) == "2.3.0"


def test_semver_dict_includes_pre_and_build_when_set() -> None:
    payload = {"major": 1, "minor": 4, "patch": 2, "pre": "rc1", "build": "abc"}
    assert format_version(payload) == "1.4.2-rc1+abc"


def test_semver_dict_requires_major_minor_patch() -> None:
    with pytest.raises(DocumentVersionError):
        format_version({"major": 2, "minor": 3})


def test_semver_dict_rejects_unknown_keys() -> None:
    with pytest.raises(DocumentVersionError):
        format_version({"major": 1, "minor": 0, "patch": 0, "extra": "oops"})


# --- Git dict shape -----------------------------------------------------------


def test_git_dict_uses_git_describe(repo_with_tag: Path) -> None:
    assert format_version({"git": True}, cwd=repo_with_tag) == "v1.0.0"


def test_git_dict_appends_suffix(repo_with_tag: Path) -> None:
    payload = {"git": True, "suffix": "(draft)"}
    assert format_version(payload, cwd=repo_with_tag) == "v1.0.0 (draft)"


def test_git_dict_with_only_suffix_when_describe_missing(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    payload = {"git": True, "suffix": "draft"}
    # No repo → describe returns empty (with a warning); the suffix alone is
    # still rendered so the user gets some signal in the title.
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert format_version(payload, cwd=not_a_repo) == "draft"


def test_git_dict_requires_git_true() -> None:
    with pytest.raises(DocumentVersionError):
        format_version({"git": False})


def test_git_dict_rejects_unknown_keys() -> None:
    with pytest.raises(DocumentVersionError):
        format_version({"git": True, "foo": "bar"})


# --- Validation errors --------------------------------------------------------


def test_unsupported_top_level_type_raises() -> None:
    with pytest.raises(DocumentVersionError):
        format_version(123)


def test_mapping_without_known_keys_raises() -> None:
    with pytest.raises(DocumentVersionError):
        format_version({"weird": True})


# --- Direct schema construction ----------------------------------------------


def test_freeform_model_strips_whitespace() -> None:
    assert FreeFormVersion(text="  hi  ").text == "hi"


def test_semver_list_model_validates() -> None:
    assert SemverListVersion(parts=[1, 0, 0]).render() == "1.0.0"


def test_semver_dict_model_validates() -> None:
    assert SemverDictVersion(major=1, minor=2, patch=3).render() == "1.2.3"


def test_git_model_requires_true() -> None:
    with pytest.raises(ValueError, match="git must be true"):
        GitVersion(git=False)
