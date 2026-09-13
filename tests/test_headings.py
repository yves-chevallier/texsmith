from pathlib import Path
import re

from texsmith.core.conversion.core import convert_documents
from texsmith.core.documents import Document


#: The sectioning commands of the ``article`` class, deepest level last. The
#: heading levels are read back from the emitted LaTeX: the writer chooses the
#: command, the ``headings`` pass chooses the level it stands for.
_SECTIONING = ("section", "subsection", "subsubsection", "paragraph", "subparagraph")


def _heading_levels(latex: str) -> list[int]:
    """``[1, 2, …]`` for each sectioning command of ``latex``, in document order."""
    levels: list[int] = []
    for match in re.finditer(r"\\(" + "|".join(_SECTIONING) + r")\*?\{", latex):
        levels.append(_SECTIONING.index(match.group(1)) + 1)
    return levels


def _render_headings(
    tmp_path: Path,
    markdown: str,
    *,
    template: str = "article",
    base_level: int = 0,
    promote_title: bool = True,
) -> list[int]:
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
    )
    return _heading_levels(bundle.documents[0].latex)


def test_headings_align_with_metadata_title(tmp_path: Path) -> None:
    levels = _render_headings(
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
    assert levels == [1, 2, 2, 1, 2]


def test_title_promotion_realigns_hierarchy(tmp_path: Path) -> None:
    levels = _render_headings(
        tmp_path,
        """# Title
## Section
### Subsection
### Subsection
## Section
### Subsection
""",
    )
    assert levels == [1, 2, 2, 1, 2]


def test_heading_offset_when_top_level_missing(tmp_path: Path) -> None:
    levels = _render_headings(
        tmp_path,
        """## Section
### Subsection
### Subsection
## Section
### Subsection
""",
    )
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
    )
    conversion = bundle.documents[0].conversion
    assert conversion is not None
    # ``Abstract`` heads the slot and is consumed by it; ``Intro`` moves up a level.
    abstract = conversion.slot_outputs["abstract"]
    assert _heading_levels(abstract) == [1]
    assert "\\section{Intro}" in abstract
