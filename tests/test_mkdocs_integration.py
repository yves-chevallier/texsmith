from collections.abc import Iterator
import hashlib
from pathlib import Path
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.adapters.plugins import material
from texsmith.adapters.transformers import register_converter, registry
from texsmith.core.config import BookConfig


ROOT = Path(__file__).resolve().parents[1]

try:  # pragma: no cover - optional dependency for this suite
    from mkdocs.commands.build import build as mkdocs_build
    from mkdocs.config import load_config
except ModuleNotFoundError:  # pragma: no cover - graceful degradation
    mkdocs_build = None  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]


class _StubConverter:
    """Simple converter that writes deterministic PDF placeholders."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self, source: str | Path, *, output_dir: Path, **_: object) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(source, Path):
            stem = source.stem or self.name
        else:
            payload = str(source)
            parsed = urlparse(payload)
            if parsed.scheme and parsed.netloc:
                stem_candidate = Path(parsed.path or "").stem
                stem = stem_candidate or self.name
            else:
                digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
                stem = f"{self.name}-{digest}"

        target = output_dir / f"{stem}.pdf"
        target.write_text(f"stub {self.name}", encoding="utf-8")
        return target


pytestmark = pytest.mark.skipif(
    mkdocs_build is None, reason="MkDocs is not installed; skipping integration test."
)


@pytest.fixture
def _stubbed_converters() -> Iterator[None]:
    converters = ("drawio", "mermaid", "fetch-image")
    originals = {key: registry.get(key) for key in converters}
    for key in converters:
        register_converter(key, _StubConverter(key))
    try:
        yield
    finally:
        for key, original in originals.items():
            register_converter(key, original)


@pytest.mark.usefixtures("_stubbed_converters")
def test_full_document_conversion(tmp_path: Path) -> None:
    assert mkdocs_build is not None
    assert load_config is not None

    config_path = ROOT / "tests" / "test_mkdocs" / "mkdocs.yml"
    site_dir = tmp_path / "site"

    config = load_config(
        config_file=str(config_path),
        site_dir=str(site_dir),
        docs_dir=str(config_path.parent / "docs"),
    )
    mkdocs_build(config)

    html_path = site_dir / "index.html"
    assert html_path.exists(), "MkDocs build did not produce index.html"

    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.md-content__inner")
    assert article is not None, "Unable to locate main article content in HTML"
    content_html = article.decode_contents()
    renderer = LaTeXRenderer(
        config=BookConfig(project_dir=site_dir),
        output_root=tmp_path / "latex-build",
        parser="html.parser",
    )
    material.register(renderer)

    latex_output = renderer.render(
        content_html,
        runtime={
            "source_dir": site_dir,
            "document_path": html_path,
            "base_level": 0,
            "numbered": True,
        },
    )

    assert latex_output.strip(), "Rendered LaTeX output is empty."

    expectations = [
        r"\chapter{MkDocs test document}",
        r"\section{Plain \textbf{Markdown} \emph{Features}}",
        r"\begin{itemize}",
        r"\begin{enumerate}",
        r"print",  # Pygments inline output contains the verbatim print call
        r"\href{https://www.mkdocs.org/}{MkDocs website}",
        r"\caption[MkDocs Logo]{MkDocs Logo}",
        (
            r"\caption[Algorithme de calcul du PGCD d'Euclide]"
            r"{Algorithme de calcul du PGCD d'Euclide}"
        ),
        (
            r"\caption[Influences des langages de programmation]"
            r"{Influences des langages de programmation}"
        ),
        r"\textbf{Python}\par",
        r"\textbf{JavaScript}\par",
        r"\begin{description}",
        r"\begin{tabularx}",
        r"\subsubsection{Heading Level 4}\label{custom-id}",
        r"\paragraph{Heading Level 5}\label{heading-level-5}\mbox{}\\",
        r"\texsmithHighlight{vulputate erat efficitur}",
        r"\sout{Deleted text}",
        r"H\textsubscript{2}O",
        r"X\textsuperscript{2}",
        r"\begin{todolist}",
        r"\done",
        r"\keystroke{Ctrl}+\keystroke{S}",
        r"\keystroke{⌘}",
        r"\begin{callout}[callout note]{A Simple Note}",
        r"\begin{callout}[callout info]{Information Box}",
        r"\begin{callout}[callout warning]{Warning}",
        r"\begin{callout}[callout success]{Success}",
    ]

    for snippet in expectations:
        assert snippet in latex_output, f"Expected to find snippet {snippet!r}"

    assert "Hello" in latex_output and "name" in latex_output
    assert "def greet(name):" in latex_output
    assert re.search(r"\\footnote\{.*footnote", latex_output) is not None
    assert r"\begin{callout}[callout note]{Expandable Section}" in latex_output
    assert r"\texsmithEmoji{😂}" in latex_output
