"""The front-matter epigraph reaches the writers, through the ``epigraph`` pass.

``epigraph: {quote, source}`` is metadata TeXSmith turns into the node a
``> {.epigraph}`` quote makes (``texsmith.passes.epigraph``); the writers
have emitted ``\\tsepigraph`` for that node all along, so these checks read
the rendered LaTeX rather than the tree.
"""

from __future__ import annotations

from pathlib import Path
import re

from texsmith.core.conversion.core import convert_documents
from texsmith.core.documents import Document


def _latex(tmp_path: Path, markdown: str, *, promote_title: bool = False) -> str:
    source = tmp_path / "doc.md"
    source.write_text(markdown, encoding="utf-8")
    document = Document.from_markdown(source, promote_title=promote_title)
    bundle = convert_documents([document], output_dir=tmp_path / "build", template="article")
    return bundle.documents[0].latex


def test_the_epigraph_follows_the_opening_section(tmp_path: Path) -> None:
    latex = _latex(
        tmp_path,
        """---
epigraph:
  quote: Tout devrait être rendu aussi simple que possible.
  source: Albert Einstein
---

# Syntaxe

Le chapitre.
""",
    )

    assert latex.count("\\tsepigraph") == 1
    assert re.search(
        r"\\section\{Syntaxe\}\s*\\tsepigraph\[source=\{Albert Einstein\}\]"
        r"\{Tout devrait être rendu aussi simple que possible\.\}",
        latex,
    ), latex


def test_an_epigraph_without_a_source_carries_no_option(tmp_path: Path) -> None:
    latex = _latex(tmp_path, "---\nepigraph:\n  quote: Sans source.\n---\n\nDu texte.\n")

    assert "\\tsepigraph{Sans source.}" in latex


def test_a_page_without_the_key_carries_no_epigraph(tmp_path: Path) -> None:
    assert "\\tsepigraph" not in _latex(tmp_path, "# Titre\n\nDu texte.\n")
