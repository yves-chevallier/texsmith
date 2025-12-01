from __future__ import annotations

import base64
import json
from pathlib import Path
import zlib

from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.mermaid import MermaidExtension


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


def test_mermaid_extension_uses_configured_base_paths(tmp_path: Path) -> None:
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text("flowchart LR\n    X --> Y\n", encoding="utf-8")

    html = render_markdown(
        "![Standalone](diagram.mmd)",
        extensions=[MermaidExtension(base_paths=[tmp_path])],
    ).html

    assert '<pre class="mermaid"' in html
    assert "X --&gt; Y" in html


def test_mermaid_extension_handles_json_pako_payload() -> None:
    diagram = "flowchart TD\n    Start --> End\n"
    payload = json.dumps({"code": diagram})
    compressed = zlib.compress(payload.encode("utf-8"))
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    url = f"https://mermaid.live/edit#pako:{encoded}"

    html = render_markdown(
        f"![JSON Example]({url})",
        extensions=MERMAID_EXTENSION,
    ).html

    assert '<pre class="mermaid"' in html
    assert "Start --&gt; End" in html


def test_packet_diagram_is_detected(tmp_path: Path) -> None:
    diagram = tmp_path / "packet.mmd"
    diagram.write_text(
        "\n".join(
            [
                "packet",
                '    0-7: "Header"',
                '    8-15: "Payload"',
            ]
        ),
        encoding="utf-8",
    )

    html = render_markdown(
        "![Packet example](packet.mmd)",
        extensions=MERMAID_EXTENSION,
        base_path=tmp_path,
    ).html

    assert '<pre class="mermaid"' in html
    assert "Header" in html


def test_mermaid_fence_preserves_attributes() -> None:
    html = render_markdown(
        "\n".join(
            [
                "```mermaid {width=60%}",
                "flowchart LR",
                "    A --> B",
                "```",
            ]
        ),
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html

    assert '<pre class="mermaid"' in html
    assert 'width="60%' in html
