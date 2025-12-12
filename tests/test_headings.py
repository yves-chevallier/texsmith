from pathlib import Path

import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.api.document import Document
from texsmith.api.pipeline import convert_documents
from texsmith.core.config import BookConfig
from texsmith.core.context import DocumentState


@pytest.fixture
def renderer() -> LaTeXRenderer:
    return LaTeXRenderer(config=BookConfig(), parser="html.parser")


def test_basic_heading_rendering(renderer: LaTeXRenderer) -> None:
    html = "<h2 id='intro'>Introduction</h2>"
    state = DocumentState()
    latex = renderer.render(
        html,
        runtime={"base_level": 0},
        state=state,
    )
    assert "\\section{Introduction}\\label{intro}" in latex
    assert state.headings == [{"level": 1, "text": "Introduction", "ref": "intro"}]


def test_inline_formatting_preserved(renderer: LaTeXRenderer) -> None:
    html = "<h3 id='intro'>Intro <strong>Bold</strong></h3>"
    latex = renderer.render(html, runtime={"base_level": 0})
    assert "\\subsection{Intro \\textbf{Bold}}\\label{intro}" in latex


def test_heading_with_nested_formatting(renderer: LaTeXRenderer) -> None:
    html = "<h2 id='mix'>Title <strong>and <em>mix</em></strong></h2>"
    latex = renderer.render(html, runtime={"base_level": 0})
    assert "\\section{Title \\textbf{and \\emph{mix}}}\\label{mix}" in latex


def test_heading_without_id_gets_slug(renderer: LaTeXRenderer) -> None:
    html = "<h2>Release Notes &amp; Compatibility</h2>"
    state = DocumentState()
    latex = renderer.render(html, runtime={"base_level": 0}, state=state)
    assert "\\section{Release Notes \\& Compatibility}\\label{release-notes-compatibility}" in latex
    assert state.headings == [
        {
            "level": 1,
            "text": "Release Notes \\& Compatibility",
            "ref": "release-notes-compatibility",
        }
    ]


def test_drop_title_runtime_flag(renderer: LaTeXRenderer) -> None:
    html = "<h1>Main Title</h1><h2>Subsection</h2>"
    state = DocumentState()
    latex = renderer.render(
        html,
        runtime={"base_level": 0, "drop_title": True},
        state=state,
    )
    assert "\\chapter{Main Title}" not in latex
    assert "\\thispagestyle{plain}" in latex
    assert "\\section{Subsection}\\label{subsection}" in latex
    assert state.headings == [{"level": 1, "text": "Subsection", "ref": "subsection"}]


def _render_headings(
    tmp_path: Path,
    markdown: str,
    *,
    template: str = "article",
    base_level: int = 0,
    promote_title: bool = True,
) -> list[dict[str, object]]:
    source = tmp_path / "doc.md"
    source.write_text(markdown, encoding="utf-8")
    document = Document.from_markdown(
        source,
        base_level=base_level,
        promote_title=promote_title,
    )
    bundle = convert_documents(
        [document],
        output_dir=tmp_path / "build",
        template=template,
        wrap_document=False,
    )
    conversion = bundle.fragments[0].conversion
    assert conversion is not None
    assert conversion.document_state is not None
    return conversion.document_state.headings


def test_headings_align_with_metadata_title(tmp_path: Path) -> None:
    headings = _render_headings(
        tmp_path,
        """---
title: Title
---
## Section
### Subsection
### Subsection
## Section
### Subsection
""",
    )
    levels = [entry["level"] for entry in headings]
    assert levels == [1, 2, 2, 1, 2]


def test_title_promotion_realigns_hierarchy(tmp_path: Path) -> None:
    headings = _render_headings(
        tmp_path,
        """# Title
## Section
### Subsection
### Subsection
## Section
### Subsection
""",
    )
    levels = [entry["level"] for entry in headings]
    assert levels == [1, 2, 2, 1, 2]


def test_heading_offset_when_top_level_missing(tmp_path: Path) -> None:
    headings = _render_headings(
        tmp_path,
        """## Section
### Subsection
### Subsection
## Section
### Subsection
""",
    )
    levels = [entry["level"] for entry in headings]
    assert levels == [1, 2, 2, 1, 2]


def test_slot_extraction_adjusts_offset(tmp_path: Path) -> None:
    source = tmp_path / "slotted.md"
    source.write_text(
        """---
title: Demo
---
# Abstract

## Intro
Text
""",
        encoding="utf-8",
    )
    document = Document.from_markdown(source, promote_title=False)
    document.assign_slot("abstract", selector="Abstract", include_document=False)

    bundle = convert_documents(
        [document],
        output_dir=tmp_path / "build",
        template="article",
        wrap_document=False,
    )
    conversion = bundle.fragments[0].conversion
    assert conversion is not None
    state = conversion.document_state
    assert state is not None
    assert [entry["level"] for entry in state.headings] == [1]
    assert state.headings[0]["text"] == "Intro"
