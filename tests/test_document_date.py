from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import subprocess

import pytest

from texsmith.core import git_version
from texsmith.core.document_date import format_date


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture(autouse=True)
def _clear_cache():
    git_version.reset_cache()
    yield
    git_version.reset_cache()


# --- Empty / no-date branches -------------------------------------------------


def test_none_value_returns_empty_string() -> None:
    assert format_date(None) == ""


def test_keyword_none_returns_empty_string() -> None:
    assert format_date("none") == ""
    assert format_date("None") == ""
    assert format_date("NONE") == ""


def test_empty_string_returns_empty_string() -> None:
    assert format_date("") == ""
    assert format_date("   ") == ""


# --- Locale-aware long form ---------------------------------------------------


def test_iso_string_renders_french_long_form() -> None:
    assert format_date("2026-03-05", language="french") == "5 mars 2026"


def test_iso_string_renders_english_long_form() -> None:
    assert format_date("2026-03-05", language="english") == "March 5, 2026"


def test_iso_string_uses_first_for_french_first_of_month() -> None:
    assert format_date("2026-03-01", language="french") == "1er mars 2026"


def test_iso_string_unknown_language_falls_back_to_english() -> None:
    assert format_date("2026-03-05", language="klingon") == "March 5, 2026"


def test_python_date_value_is_rendered() -> None:
    assert format_date(date(2026, 7, 14), language="french") == "14 juillet 2026"


def test_python_datetime_value_is_rendered() -> None:
    from datetime import timezone

    moment = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
    assert format_date(moment, language="french") == "31 décembre 2026"


# --- Today --------------------------------------------------------------------


def test_today_keyword_uses_injected_date() -> None:
    fixed = date(2026, 1, 15)
    assert format_date("today", language="french", today=fixed) == "15 janvier 2026"
    assert format_date("today", language="english", today=fixed) == "January 15, 2026"


# --- Commit -------------------------------------------------------------------


def test_commit_keyword_uses_last_commit_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(git_version, "git_commit_date", lambda **_: date(2026, 4, 12))
    rendered = format_date("commit", language="french", cwd=tmp_path)
    assert rendered == "12 avril 2026"


def test_commit_keyword_real_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": "2026-04-12T12:00:00",
        "GIT_COMMITTER_DATE": "2026-04-12T12:00:00",
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
        env=env,
    )
    assert format_date("commit", language="french", cwd=repo) == "12 avril 2026"


def test_commit_without_repo_returns_empty(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert format_date("commit", cwd=not_a_repo) == ""


# --- Free-form ----------------------------------------------------------------


def test_free_form_string_passes_through_when_not_iso() -> None:
    assert format_date("Spring 2026") == "Spring 2026"


def test_invalid_iso_falls_back_to_free_form() -> None:
    assert format_date("2026-13-99") == "2026-13-99"


# --- Type errors --------------------------------------------------------------


def test_unsupported_type_raises_type_error() -> None:
    with pytest.raises(TypeError):
        format_date(12345)
    with pytest.raises(TypeError):
        format_date(["a", "list"])
