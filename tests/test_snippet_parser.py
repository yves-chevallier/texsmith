from __future__ import annotations

from pathlib import Path
import textwrap

from bs4 import BeautifulSoup

from texsmith.adapters.plugins import snippet


def _build_snippet_block(tmp_path: Path, body: str) -> snippet.SnippetBlock:
    html = f"""
    <div class="snippet">
      <pre><code class="language-md">{body}</code></pre>
    </div>
    """
    soup = BeautifulSoup(textwrap.dedent(html), "html.parser")
    element = soup.find("div")
    assert element is not None
    host_path = tmp_path / "host.md"
    host_path.write_text("host", encoding="utf-8")
    block = snippet._extract_snippet_block(element, host_path=host_path)
    assert block is not None
    return block


def test_snippet_uses_press_template_override(tmp_path: Path) -> None:
    raw = """
    ---
    press:
      template: article
    ---
    # Hello
    """
    block = _build_snippet_block(tmp_path, textwrap.dedent(raw).strip())

    assert block.template_id == "article"
    assert "template" not in block.template_overrides.get("press", {})
