from __future__ import annotations

import base64
from pathlib import Path
import zlib

from texsmith.adapters.markdown import render_markdown


MERMAID_EXTENSION = ["texsmith.mermaid:MermaidExtension"]


def test_mermaid_extension_inlines_local_file(tmp_path: Path) -> None:
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text("flowchart LR\n    A --> B\n", encoding="utf-8")

    html = render_markdown(
        "![Build pipeline](diagram.mmd)",
        extensions=MERMAID_EXTENSION,
        base_path=tmp_path,
    ).html

    assert '<pre class="mermaid"' in html
    assert "flowchart LR" in html
    assert "%% Build pipeline" in html


def test_mermaid_extension_decodes_pako_urls() -> None:
    diagram = "flowchart LR\n    A --> B\n"
    compressed = zlib.compress(diagram.encode("utf-8"))
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    url = f"https://mermaid.live/edit#pako:{encoded[:30]}\n{encoded[30:]}"

    html = render_markdown(
        f"![Online Diagram]({url})",
        extensions=MERMAID_EXTENSION,
    ).html

    assert '<pre class="mermaid"' in html
    assert "flowchart LR" in html
    assert "%% Online Diagram" in html
