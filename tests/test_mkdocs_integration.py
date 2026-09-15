"""The mini site's PDF export: the pages' sources through the tmark reader path.

``on_post_build`` builds every configured book from the stored page sources
(``specs/migration/web-profile.md`` step 4): the ``.tex`` is always written;
the PDF is built when ``TEXSMITH_BUILD=1`` and tectonic can be provisioned.
"""

from collections.abc import Iterator
import hashlib
import os
from pathlib import Path
import shutil
import ssl
import urllib.error
from urllib.parse import urlparse

import pytest

from texsmith.adapters.transformers import register_converter, registry


ROOT = Path(__file__).resolve().parents[1]

try:  # pragma: no cover - optional dependency for this suite
    from mkdocs.commands.build import build as mkdocs_build
    from mkdocs.config import load_config
except ModuleNotFoundError:  # pragma: no cover - graceful degradation
    mkdocs_build = None  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]


def _placeholder_pdf(label: str) -> bytes:
    """A minimal, valid one-page PDF carrying ``label``."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((10, 50), label)
    payload = document.tobytes()
    document.close()
    return payload


class _StubConverter:
    """Simple converter that writes deterministic PDF placeholders.

    The placeholder is a real one-page PDF, not a text file: the export test
    hands the book to tectonic, and ``\\includegraphics`` refuses anything
    that is not a PDF.
    """

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
        target.write_bytes(_placeholder_pdf(f"stub {self.name}"))
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


def build_mini_site(tmp_path: Path) -> tuple[Path, Path]:
    """Build the mini site in ``tmp_path``; return ``(site_dir, press_dir)``."""
    assert mkdocs_build is not None
    assert load_config is not None
    source = ROOT / "tests" / "test_mkdocs"
    config_path = tmp_path / "mkdocs.yml"
    shutil.copy(source / "mkdocs.yml", config_path)
    site_dir = tmp_path / "site"
    config = load_config(
        config_file=str(config_path),
        site_dir=str(site_dir),
        docs_dir=str(source / "docs"),
    )
    mkdocs_build(config)
    return site_dir, tmp_path / "press"


def _tectonic_binary() -> Path | None:
    from texsmith.adapters.latex.tectonic import (
        BundledToolError,
        _install_dir,
        select_tectonic_binary,
    )

    bundled = _install_dir() / "tectonic"
    system = shutil.which("tectonic")
    if not bundled.exists() and system is None and not os.environ.get("CI"):
        return None
    try:
        return select_tectonic_binary().path
    except BundledToolError:
        return None
    except Exception:  # pragma: no cover - network failures
        return None


@pytest.mark.usefixtures("_stubbed_converters")
def test_book_is_built_from_the_page_sources(tmp_path: Path) -> None:
    """The ``.tex`` of the book comes from the pages' sources through tmark."""
    _site_dir, press = build_mini_site(tmp_path)
    book = press / "mini"
    main = book / "mini.tex"
    assert main.exists(), "the book's main .tex was not written"

    # The exact sources the PDF was built from are kept next to it.
    stored = book / "sources" / "constructs.md"
    assert stored.exists()
    source = stored.read_text(encoding="utf-8")
    assert "#(fw:watchdog)" in source
    assert "req:" in source and "REQ-{n:03d}" in source  # site-wide declaration merged

    pages = {path.name: path.read_text(encoding="utf-8") for path in (book / "pages").glob("*.tex")}
    constructs = pages["constructs-md.tex"]
    numbering = pages["numbering-md.tex"]
    # The site's numbers, on print: the writer numbers user counters itself.
    assert "FW-01" in constructs and "FW-04" in constructs
    assert "FW-05" in numbering and "REQ-100" in numbering
    assert "\\label{fw:watchdog}" in constructs
    # Cross-page counter references resolve inside the book.
    assert "[?fw:watchdog]" not in numbering
    assert "FW-01" in numbering
    # TMark constructs the HTML path never carried survive on the source path.
    assert "\\tsindex" in constructs
    assert "\\tsaside" in constructs
    assert "raw LaTeX" not in constructs  # nothing raw in this page: no leak either way
    assert "in print" in constructs and "on the site" not in constructs


#: What a build that reached for the network and failed raises, directly or
#: as the cause of whatever wrapped it.
_NETWORK_ERRORS = (
    urllib.error.URLError,
    ssl.SSLError,
    ConnectionError,
    TimeoutError,
)


def _network_failure(exc: BaseException) -> bool:
    """True when ``exc`` or anything it was raised from is a network error."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, _NETWORK_ERRORS):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


@pytest.mark.usefixtures("_stubbed_converters")
def test_book_pdf_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``TEXSMITH_BUILD=1`` compiles the book; skipped without tectonic.

    Provisioning tectonic and its TeX bundle reaches the network, and a CI
    runner that cannot verify a certificate is not a regression of this
    repository: such a build is skipped, like a missing tectonic.
    """
    if _tectonic_binary() is None:
        pytest.skip("tectonic cannot be provisioned")
    monkeypatch.setenv("TEXSMITH_BUILD", "1")
    try:
        _site_dir, press = build_mini_site(tmp_path)
    except Exception as exc:
        if _network_failure(exc):
            pytest.skip(f"the build could not reach the network: {exc}")
        raise
    pdf = press / "mini" / "mini.pdf"
    assert pdf.exists(), "the PDF export did not produce mini.pdf"
    assert pdf.stat().st_size > 1000
