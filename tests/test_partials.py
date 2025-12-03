from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.api import Document, TemplateSession
from texsmith.core.conversion.debug import ConversionError
from texsmith.core.templates import load_template_runtime


def _write_template(
    root: Path, *, override_content: str | None = None, required: list[str] | None = None
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    manifest_lines = [
        "[latex.template]",
        'name = "partial-template"',
        'version = "0.0.0"',
        'entrypoint = "template.tex"',
    ]
    if override_content is not None:
        manifest_lines.append('override = ["strong.tex"]')
    if required:
        required_list = ", ".join(f'"{item}"' for item in required)
        manifest_lines.append(f"required_partials = [{required_list}]")
    (root / "template.tex").write_text(
        r"\VAR{extra_packages}" "\n" r"\VAR{mainmatter}", encoding="utf-8"
    )
    if override_content is not None:
        overrides_dir = root / "overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)
        (overrides_dir / "strong.tex").write_text(override_content, encoding="utf-8")
    (root / "manifest.toml").write_text("\n".join(manifest_lines), encoding="utf-8")
    return root


def _write_fragment(
    root: Path,
    *,
    name: str,
    partial_name: str | None = None,
    partial_content: str | None = None,
    required: list[str] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "noop.tex").write_text("", encoding="utf-8")
    manifest_lines = [
        f'name = "{name}"',
        'description = "partial test fragment"',
    ]
    if partial_name and partial_content is not None:
        manifest_lines.append(f'partials = ["{partial_name}"]')
        (root / partial_name).write_text(partial_content, encoding="utf-8")
    if required:
        required_list = ", ".join(f'"{item}"' for item in required)
        manifest_lines.append(f"required_partials = [{required_list}]")
    manifest_lines.append(
        'files = [{ path = "noop.tex", type = "inline", slot = "extra_packages" }]'
    )
    (root / "fragment.toml").write_text("\n".join(manifest_lines), encoding="utf-8")
    return root


def _render_markdown(
    *, tmp_path: Path, template_root: Path, fragment_paths: list[Path], body: str
) -> str:
    fragment_lines = "\n".join(f"    - {path.as_posix()}" for path in fragment_paths)
    fragments_block = ""
    if fragment_lines:
        fragments_block = f"  fragments:\n{fragment_lines}\n"
    content = f"---\npress:\n{fragments_block}---\n{body}\n"
    md = tmp_path / "doc.md"
    md.write_text(content, encoding="utf-8")

    session = TemplateSession(load_template_runtime(str(template_root)))
    session.add_document(Document.from_markdown(md))
    result = session.render(tmp_path / "build")
    return result.main_tex_path.read_text(encoding="utf-8")


def test_template_partials_override_fragments(tmp_path: Path) -> None:
    template_root = _write_template(
        tmp_path / "template",
        override_content="TEMPLATE<<\\VAR{text}>>",
    )
    fragment_root = _write_fragment(
        tmp_path / "fragment",
        name="fragment-a",
        partial_name="strong.tex",
        partial_content="FRAGMENT<<\\VAR{text}>>",
    )

    output = _render_markdown(
        tmp_path=tmp_path,
        template_root=template_root,
        fragment_paths=[fragment_root],
        body="**bold**",
    )

    assert "TEMPLATE<<" in output
    assert "FRAGMENT<<" not in output


def test_fragment_partial_overrides_core_default(tmp_path: Path) -> None:
    template_root = _write_template(tmp_path / "template-default")
    fragment_root = _write_fragment(
        tmp_path / "fragment-default",
        name="fragment-b",
        partial_name="strong.tex",
        partial_content="FRAGMENT<<\\VAR{text}>>",
    )

    output = _render_markdown(
        tmp_path=tmp_path,
        template_root=template_root,
        fragment_paths=[fragment_root],
        body="**bold**",
    )

    assert "FRAGMENT<<" in output
    assert "\\textbf" not in output


def test_fragment_partial_conflict_raises(tmp_path: Path) -> None:
    template_root = _write_template(tmp_path / "template-conflict")
    fragment_a = _write_fragment(
        tmp_path / "fragment-conflict-a",
        name="fragment-c",
        partial_name="strong.tex",
        partial_content="A<<\\VAR{text}>>",
    )
    fragment_b = _write_fragment(
        tmp_path / "fragment-conflict-b",
        name="fragment-d",
        partial_name="strong.tex",
        partial_content="B<<\\VAR{text}>>",
    )

    with pytest.raises(ConversionError):
        _render_markdown(
            tmp_path=tmp_path,
            template_root=template_root,
            fragment_paths=[fragment_a, fragment_b],
            body="**bold**",
        )


def test_required_partial_missing_triggers_error(tmp_path: Path) -> None:
    template_root = _write_template(tmp_path / "template-required")
    fragment_root = _write_fragment(
        tmp_path / "fragment-required",
        name="fragment-e",
        required=["missing-partial"],
    )

    with pytest.raises(ConversionError):
        _render_markdown(
            tmp_path=tmp_path,
            template_root=template_root,
            fragment_paths=[fragment_root],
            body="**bold**",
        )
