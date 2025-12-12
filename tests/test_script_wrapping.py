from __future__ import annotations

from pathlib import Path
import textwrap

from texsmith.api.document import Document
from texsmith.api.templates import get_template


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def test_scripts_wrapped_in_moving_arguments(tmp_path: Path) -> None:
    doc_path = _write(
        tmp_path,
        "sample.md",
        "# Tibetan (བོད་ ཡིག Bengali বাংলা)\n\nCaption: বাংলা",
    )
    session = get_template("article")
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "build"
    result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "\\texttibetan{བོད" in content
    assert "\\textbengali{বাংলা}" in content
    assert "\\section{Tibetan (" in content
    usage = result.context.get("fonts", {}).get("script_usage")
    assert usage, "Expected script usage to be propagated to template context"
    slugs = {entry.get("slug") for entry in usage}
    assert {"tibetan", "bengali"} <= slugs


def test_lonely_greek_prefers_math_mode(tmp_path: Path) -> None:
    doc_path = _write(tmp_path, "greek.md", "# Omega (Ω) / Aleph (ℵ)")
    session = get_template("article")
    session.add_document(Document.from_markdown(doc_path))

    build_dir = tmp_path / "build"
    result = session.render(build_dir)

    content = result.main_tex_path.read_text(encoding="utf-8")
    assert "$\\Omega$" in content
    assert "$\\aleph$" in content
    assert "\\textgreek" not in content
