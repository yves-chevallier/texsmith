from __future__ import annotations

from pathlib import Path
import textwrap

from texsmith.core.conversion import renderer as renderer_module
from texsmith.core.documents import Document
from texsmith.core.templates import load_template_runtime
from texsmith.core.templates.session import TemplateSession


def _write_markdown(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _create_minimal_template(tmp_path: Path, *, engine: str, shell_escape: bool) -> Path:
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    (template_dir / "manifest.toml").write_text(
        textwrap.dedent(
            f"""
            [compat]
            texsmith = ">=0.1,<2.0"

            [latex.template]
            name = "demo"
            version = "0.0.1"
            entrypoint = "template.tex"
            engine = "{engine}"
            shell_escape = {str(bool(shell_escape)).lower()}

            [latex.template.slots.mainmatter]
            default = true
            depth = "section"
            """
        ).strip(),
        encoding="utf-8",
    )
    (template_dir / "template.tex").write_text(
        textwrap.dedent(
            r"""
            \documentclass{article}
            \begin{document}
            \VAR{mainmatter}
            \end{document}
            """
        ).strip(),
        encoding="utf-8",
    )
    return template_dir


def test_renderer_reuses_fallback_manager_for_multiple_scans(tmp_path, monkeypatch) -> None:
    template_dir = _create_minimal_template(tmp_path, engine="lualatex", shell_escape=False)
    runtime = load_template_runtime(template_dir)
    session = TemplateSession(runtime=runtime)

    doc_path = _write_markdown(
        tmp_path,
        "doc.md",
        """
        ---
        title: Fancy
        ---
        Hello world
        """,
    )
    session.add_document(Document.from_markdown(doc_path))

    seen_instances: set[int] = set()
    calls: list[str] = []

    def _fake_scan(self, text: str, **_kwargs) -> list[dict]:
        seen_instances.add(id(self))
        calls.append(text)
        return []

    monkeypatch.setattr(renderer_module.FallbackManager, "scan_text", _fake_scan)

    session.render(tmp_path / "build")

    assert len(calls) == 2
    assert len(seen_instances) == 1
