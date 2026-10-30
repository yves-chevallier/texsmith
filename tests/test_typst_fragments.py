"""A fragment's Typst pieces reach the Typst render, and only it."""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.core.conversion import ConversionRequest
from texsmith.core.conversion.typst import render_typst_document
from texsmith.core.documents import Document
from texsmith.core.fragments import FragmentDefinition, render_fragments
from texsmith.core.fragments.base import FragmentPiece
from texsmith.core.templates.manifest import TemplateError


def _fragment(root: Path) -> Path:
    """A ``stamp`` fragment with a LaTeX package and a Typst module + call."""
    root.mkdir()
    (root / "stamp.jinja.sty").write_text(
        "\\newcommand\\stamp{\\VAR{ stamp_text }}\n", encoding="utf-8"
    )
    (root / "stamp.typ").write_text("#let stamp(body) = text(fill: red, body)\n", encoding="utf-8")
    (root / "stamp.jinja.typ").write_text("#stamp[{{ stamp_text }}]\n", encoding="utf-8")
    (root / "fragment.toml").write_text(
        "\n".join(
            [
                'name = "stamp"',
                "",
                "[[files]]",
                'path = "stamp.jinja.sty"',
                'output = "stamp"',
                "",
                "[[files]]",
                'path = "stamp.typ"',
                'output = "stamp"',
                'backend = "typst"',
                "",
                "[[files]]",
                'path = "stamp.jinja.typ"',
                'type = "inline"',
                'backend = "typst"',
                "",
                "[attributes.stamp_text]",
                'default = "draft"',
                'sources = ["stamp.text"]',
            ]
        ),
        encoding="utf-8",
    )
    return root


def _render(tmp_path: Path, front_matter: str, **request: object) -> tuple[str, Path]:
    fragment = _fragment(tmp_path / "stamp")
    source = tmp_path / "doc.md"
    source.write_text(
        f"---\npress:\n  fragments:\n    append:\n      - {fragment}\n{front_matter}---\n\nBody\n",
        encoding="utf-8",
    )
    document = Document.from_markdown(source).prepare_for_conversion()
    out_dir = tmp_path / "out"
    payload = render_typst_document(
        document,
        ConversionRequest(documents=[Path(source)], **request),  # type: ignore[arg-type]
        output_dir=out_dir,
    )
    return payload, out_dir


def test_a_piece_names_its_backend(tmp_path: Path) -> None:
    root = _fragment(tmp_path / "stamp")
    definition = FragmentDefinition.from_manifest(root / "fragment.toml")
    assert [piece.backend for piece in definition.pieces] == ["latex", "typst", "typst"]
    assert definition.pieces[1].output_filename("stamp") == "stamp.typ"
    assert definition.pieces[1].injection("stamp.typ") == '#import "stamp.typ": *'


def test_an_unknown_backend_is_refused(tmp_path: Path) -> None:
    (tmp_path / "x.typ").write_text("", encoding="utf-8")
    with pytest.raises(TemplateError, match="Unknown fragment file backend 'html'"):
        FragmentPiece.from_mapping({"path": "x.typ", "backend": "html"}, base_dir=tmp_path)


def test_the_latex_render_ignores_the_typst_pieces(tmp_path: Path) -> None:
    root = _fragment(tmp_path / "stamp")
    result = render_fragments([str(root)], context={}, output_dir=tmp_path / "out", backend="latex")
    assert result.variable_injections == {"extra_packages": ["\\usepackage{stamp}"]}
    assert [path.name for path in result.written] == ["stamp.sty"]


def test_the_typst_render_writes_the_module_and_injects_the_call(tmp_path: Path) -> None:
    root = _fragment(tmp_path / "stamp")
    result = render_fragments(
        [str(root)],
        context={},
        output_dir=tmp_path / "out",
        overrides={"stamp": {"text": "secret"}},
        backend="typst",
    )
    assert result.variable_injections == {
        "extra_packages": ['#import "stamp.typ": *', "#stamp[secret]"]
    }
    assert (tmp_path / "out" / "stamp.typ").read_text(encoding="utf-8").startswith("#let stamp")
    assert not (tmp_path / "out" / "stamp.sty").exists()


def test_a_fragment_without_typst_pieces_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "latex-only"
    root.mkdir()
    (root / "only.jinja.sty").write_text("\\relax\n", encoding="utf-8")
    result = render_fragments(
        [str(root / "only.jinja.sty")], context={}, output_dir=tmp_path / "out", backend="typst"
    )
    assert result.variable_injections == {}
    assert result.written == []


def test_the_article_template_receives_the_fragment(tmp_path: Path) -> None:
    payload, out_dir = _render(tmp_path, "stamp:\n  text: secret\n", template="article")
    assert '#import "stamp.typ": *\n#stamp[secret]' in payload
    # Before the title block and the body, after the set rules.
    assert payload.index("#stamp[secret]") > payload.index("#set page(")
    assert payload.index("#stamp[secret]") < payload.index("Body")
    assert (out_dir / "stamp.typ").exists()


def test_the_standalone_document_receives_the_fragment(tmp_path: Path) -> None:
    payload, _ = _render(tmp_path, "")
    assert '#import "stamp.typ": *\n#stamp[draft]' in payload
    assert payload.index("#stamp[draft]") < payload.index("Body")


def test_no_fragment_leaves_the_article_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("Body\n", encoding="utf-8")
    document = Document.from_markdown(source).prepare_for_conversion()
    payload = render_typst_document(
        document,
        ConversionRequest(documents=[Path(source)], template="article"),
        output_dir=tmp_path / "out",
    )
    assert "#import" not in payload.split("#set par(justify: true)")[1].split("Body")[0]


def test_a_template_without_the_variable_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "tpl"
    root.mkdir()
    (root / "manifest.toml").write_text(
        "\n".join(
            [
                "[latex.template]",
                'name = "bare"',
                'version = "0.0.1"',
                'entrypoint = "template.tex"',
                "",
                "[typst.template]",
                'name = "bare"',
                'version = "0.0.1"',
                'entrypoint = "template.typ"',
            ]
        ),
        encoding="utf-8",
    )
    (root / "template.tex").write_text("\\VAR{mainmatter}\n", encoding="utf-8")
    (root / "template.typ").write_text("{{ mainmatter }}\n", encoding="utf-8")
    with pytest.raises(TemplateError, match="doesn't declare variable 'extra_packages'"):
        _render(tmp_path, "", template=str(root))
