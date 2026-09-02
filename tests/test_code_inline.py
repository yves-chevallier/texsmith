"""Inline code breaking (``code.inline``) and plain typewriter mode."""

from pathlib import Path
from typing import Any

from texsmith.core.code_options import (
    ALL_INLINE_BREAKS,
    DEFAULT_INLINE_BREAKS,
    normalise_inline_options,
)
from texsmith.core.documents import Document
from texsmith.core.templates import load_template_runtime
from texsmith.core.templates.session import TemplateSession


BODY = "Voir `texsmith.core.conversion_options` puis `#!python some_long.name` ici.\n"


def _render(tmp_path: Path, code_options: dict[str, Any] | None, body: str = BODY) -> str:
    md = tmp_path / "doc.md"
    md.write_text(body, encoding="utf-8")

    session = TemplateSession(load_template_runtime("article"))
    if code_options:
        session.update_options({"code": code_options})
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")
    return result.main_tex_path.read_text(encoding="utf-8")


def test_default_breaks_only_on_hyphens(tmp_path: Path) -> None:
    tex = _render(tmp_path, None, "Voir `some_long.name-here` ici.\n")

    assert "\\texttt{some\\_long.name-\\allowbreak{}here}" in tex


def test_declared_breaks_apply_to_plain_inline_code(tmp_path: Path) -> None:
    tex = _render(tmp_path, {"inline": {"breaks": "_./"}})

    assert (
        "\\texttt{texsmith.\\allowbreak{}core.\\allowbreak{}conversion\\_\\allowbreak{}options}"
        in tex
    )


def test_declared_breaks_apply_to_highlighted_inline_code(tmp_path: Path) -> None:
    tex = _render(tmp_path, {"inline": {"breaks": "_."}})

    # The break lands inside the payload; the ``\PY{token}`` marker is intact.
    assert "\\PY{n}{some\\PYZus{}\\allowbreak{}long}" in tex
    assert "\\PY{o}{.\\allowbreak{}}" in tex


def test_plain_mode_drops_highlighting_of_inline_code(tmp_path: Path) -> None:
    tex = _render(tmp_path, {"inline": {"plain": True, "breaks": "_."}})

    assert "\\texttt{some\\_\\allowbreak{}long.\\allowbreak{}name}" in tex
    assert "\\PY{n}{some" not in tex


def test_plain_mode_keeps_code_blocks_highlighted(tmp_path: Path) -> None:
    body = "Voir `some_long.name` ici.\n\n```python\nprint('hi')\n```\n"
    tex = _render(tmp_path, {"inline": {"plain": True}}, body)

    assert "\\texttt{some\\_long.name}" in tex
    assert "\\PY{" in tex


def test_plain_mode_bypasses_minted_for_inline_code(tmp_path: Path) -> None:
    tex = _render(tmp_path, {"engine": "minted", "inline": {"plain": True, "breaks": "_."}})

    assert "\\mintinline" not in tex
    assert "\\texttt{some\\_\\allowbreak{}long.\\allowbreak{}name}" in tex


def test_breaks_all_covers_common_punctuation(tmp_path: Path) -> None:
    tex = _render(tmp_path, {"inline": {"breaks": "all"}}, "Voir `a_b.c/d` ici.\n")

    assert "\\texttt{a\\_\\allowbreak{}b.\\allowbreak{}c/\\allowbreak{}d}" in tex


def test_breaks_none_disables_break_points(tmp_path: Path) -> None:
    tex = _render(tmp_path, {"inline": {"breaks": "none"}}, "Voir `a-b` ici.\n")

    assert "\\texttt{a-b}" in tex


def test_normalise_inline_options_defaults() -> None:
    assert normalise_inline_options(None) == {"plain": False, "breaks": DEFAULT_INLINE_BREAKS}


def test_normalise_inline_options_shorthands() -> None:
    assert normalise_inline_options(True)["plain"] is True
    assert normalise_inline_options("_./")["breaks"] == "_./"
    assert normalise_inline_options({"breaks": True})["breaks"] == ALL_INLINE_BREAKS
    assert normalise_inline_options({"plain": "yes"})["plain"] is True


def test_normalise_inline_options_drops_alphanumerics() -> None:
    # Letters and digits would break words apart and could collide with the
    # ``\allowbreak{}`` macro inserted after each break opportunity.
    assert normalise_inline_options({"breaks": "a_1. /"})["breaks"] == "_./"


def test_normalise_inline_options_inherits_fallback() -> None:
    fallback = {"plain": True, "breaks": "_."}

    assert normalise_inline_options({"breaks": "/"}, fallback) == {"plain": True, "breaks": "/"}
    assert normalise_inline_options({"plain": False}, fallback) == {"plain": False, "breaks": "_."}
