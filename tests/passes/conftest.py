"""The pass test harness (``specs/migration/python-ir-and-passes.md`` §3, Tests).

Layout, per pass::

    tests/passes/<pass>/<case>.md         the authored input
    tests/passes/<pass>/<case>.in.json    ``tmark parse`` of it (``make ir-fixtures``)
    tests/passes/<pass>/<case>.out.json   the expected ``structural()`` result
    tests/passes/<pass>/<case>.diag.json  the expected ``[code, span, message]`` list

``harness.load(pass, case)`` builds a :class:`Document` from the committed
``.in.json`` (parsing the ``.md`` live when the JSON is missing, so a new
case can be authored before the fixtures are refreshed); ``harness.run(name,
document, ...)`` runs one registered pass over a :class:`PassContext` built
on an in-memory :class:`FileTable` and a :class:`MemoryLoader`. No HTML.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import pytest

from texsmith.adapters.transformers import registry as converter_registry
from texsmith.core.conversion.inputs import InputKind, SlotOptions
from texsmith.core.documents import Document, TitleStrategy
from texsmith.core.front_matter import split_front_matter
from texsmith.diagnostics import DiagnosticSink, FileTable
from texsmith.fonts.fallback import FallbackEntry, FallbackIndex, FallbackLookup
from texsmith.fonts.scripts import ScriptDetector
from texsmith.ir import codec
from texsmith.passes import REGISTRY, IdAllocator, PassContext, SlotTemplate, build_pipeline
from texsmith.readers.loader import MemoryLoader
from texsmith.readers.tmark import parse_payload


FIXTURES = Path(__file__).resolve().parent


@dataclass(slots=True)
class Harness:
    """Fixture helpers shared by the pass tests."""

    root: Path = FIXTURES
    last_ctx: PassContext | None = None

    def case_dir(self, pass_name: str) -> Path:
        return self.root / pass_name

    def source(self, pass_name: str, case: str) -> Path:
        return self.case_dir(pass_name) / f"{case}.md"

    def payload(self, pass_name: str, case: str) -> dict[str, Any]:
        """The ``tmark parse`` JSON of a case (committed, else parsed live)."""
        committed = self.case_dir(pass_name) / f"{case}.in.json"
        if committed.exists():
            return json.loads(committed.read_text(encoding="utf-8"))
        source = self.source(pass_name, case)
        return parse_payload(source.read_text(encoding="utf-8"), file_id=0, name=str(source))

    def load(
        self,
        pass_name: str,
        case: str,
        *,
        title_strategy: TitleStrategy = TitleStrategy.KEEP,
        base_level: int = 0,
        numbered: bool = True,
        slot_options: Mapping[str, SlotOptions] | None = None,
    ) -> Document:
        """A prepared :class:`Document` over the case's IR."""
        source = self.source(pass_name, case)
        text = source.read_text(encoding="utf-8")
        files = FileTable()
        files.add(source, text)
        front_matter, _body = split_front_matter(text)
        document = Document(
            source_path=source,
            kind=InputKind.MARKDOWN,
            _html="",
            _front_matter=front_matter,
            base_level=base_level,
            title_strategy=title_strategy,
            numbered=numbered,
            reader="tmark",
            ir=codec.decode_document(self.payload(pass_name, case)),
            files=files,
        )
        if slot_options:
            document.slot_options.update(slot_options)
        return document.prepare_for_conversion()

    def context(
        self,
        document: Document,
        *,
        contexts: tuple[Mapping[str, Any], ...] | None = None,
        template: SlotTemplate | None = None,
        loader: MemoryLoader | None = None,
        include_paths: tuple[Path, ...] = (),
        output_dir: Path | None = None,
        backend: str = "latex",
        code: Mapping[str, Any] | None = None,
        doi_fetcher: Any = None,
    ) -> PassContext:
        ids = IdAllocator()
        if document.ir is not None:
            ids.observe(document.ir)
        ctx = PassContext(
            files=document.files,
            ids=ids,
            diagnostics=DiagnosticSink(document.files),
            loader=loader or MemoryLoader(),
            include_paths=include_paths,
            output_dir=output_dir if output_dir is not None else self.root,
            contexts=contexts if contexts is not None else (document.front_matter,),
            template=template or SlotTemplate(),
            backend=backend,
            code=dict(code or {}),
            doi_fetcher=doi_fetcher,
        )
        self.last_ctx = ctx
        return ctx

    def run(
        self,
        pass_name: str,
        document: Document,
        ctx: PassContext | None = None,
        **ctx_kwargs: Any,
    ) -> Document:
        """Run the registered pass ``pass_name`` once."""
        build_pipeline()  # registers the bundled passes
        active = ctx if ctx is not None else self.context(document, **ctx_kwargs)
        return REGISTRY[pass_name].run(document, active)

    @staticmethod
    def structural(document: Document) -> dict[str, Any]:
        assert document.ir is not None
        return codec.structural(document.ir)

    @staticmethod
    def diagnostics(ctx: PassContext) -> list[list[Any]]:
        return [
            [record.code, [record.span.file, record.span.start, record.span.end], record.message]
            for record in ctx.diagnostics
        ]

    def expected(self, pass_name: str, case: str) -> dict[str, Any]:
        return json.loads((self.case_dir(pass_name) / f"{case}.out.json").read_text("utf-8"))

    def expected_diagnostics(self, pass_name: str, case: str) -> list[list[Any]]:
        path = self.case_dir(pass_name) / f"{case}.diag.json"
        if not path.exists():
            return []
        return json.loads(path.read_text("utf-8"))


@pytest.fixture
def harness() -> Harness:
    return Harness()


# ---------------------------------------------------------------------------
# Fakes for the passes that touch processes, the network or font metadata
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass(slots=True)
class FakeConverter:
    """A converter strategy writing a stub artefact and recording its calls.

    ``name`` is the registry slot it stands in for; the artefact is named after
    the source (its stem, or a digest of the text) with ``.png`` when the call
    asks for ``format="png"``, else ``.pdf``.
    """

    name: str
    calls: list[dict[str, Any]] = field(default_factory=list)
    fail: Exception | None = None

    def __call__(self, source: Any, *, output_dir: Path, **options: Any) -> Path:
        self.calls.append({"source": source, "output_dir": Path(output_dir), **options})
        if self.fail is not None:
            raise self.fail
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fmt = str(options.get("format", "pdf") or "pdf").lower()
        suffix = ".png" if fmt == "png" else ".pdf"
        if isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
            stem = Path(source).stem
        else:
            import hashlib

            stem = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:12]
        artefact = output_dir / f"{self.name}-{stem}{suffix}"
        payload = _PNG_MAGIC if suffix == ".png" else b"%PDF-1.4\n%fake\n"
        artefact.write_bytes(payload + f"{self.name}:{stem}".encode())
        return artefact


class FakeFetch(FakeConverter):
    """The ``fetch-image`` stand-in: a PNG named after the URL's basename."""

    def __call__(self, source: Any, *, output_dir: Path, **options: Any) -> Path:
        self.calls.append({"source": source, "output_dir": Path(output_dir), **options})
        if self.fail is not None:
            raise self.fail
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        from urllib.parse import urlparse

        name = Path(urlparse(str(source)).path).name or "remote"
        suffix = str(options.get("output_suffix") or Path(name).suffix or ".png")
        if suffix == ".svg" and options.get("convert", True):
            suffix = ".pdf"  # the real strategy rasterises/converts SVG unless told not to
        artefact = output_dir / f"fetched-{Path(name).stem}{suffix}"
        artefact.write_bytes(_PNG_MAGIC + str(source).encode("utf-8"))
        return artefact


@pytest.fixture
def fake_converters() -> Any:
    """Fake ``svg``, ``drawio``, ``mermaid``, ``image`` and ``fetch-image`` strategies.

    Registered for the test and restored afterwards; returns ``{name: fake}``.
    """
    names = ("svg", "drawio", "mermaid", "image", "fetch-image")
    saved = {name: converter_registry.get(name) for name in names}
    fakes: dict[str, FakeConverter] = {
        name: (FakeFetch(name) if name == "fetch-image" else FakeConverter(name)) for name in names
    }
    for name, fake in fakes.items():
        converter_registry.register(name, fake)
    try:
        yield fakes
    finally:
        for name, strategy in saved.items():
            converter_registry.register(name, strategy)


def _entry(name: str, start: int, end: int, group: str, font: str | None) -> FallbackEntry:
    payload = {"name": font, "styles": ["regular", "bold"], "extension": ".otf"} if font else {}
    return FallbackEntry(name=name, start=start, end=end, group=group, font=payload)


#: A small Unicode-block → script table standing in for the Noto/ucharclasses index.
FAKE_SCRIPT_INDEX: tuple[FallbackEntry, ...] = (
    _entry("BasicLatin", 0x0000, 0x024F, "Latin", None),
    _entry("CombiningDiacriticalMarks", 0x0300, 0x036F, "Diacritics", "NotoSans"),
    _entry("Greek", 0x0370, 0x03FF, "Greek", "NotoSansGreek"),
    _entry("Cyrillic", 0x0400, 0x04FF, "Cyrillics", "NotoSans"),
    _entry("Tibetan", 0x0F00, 0x0FFF, "Tibetan", "NotoSerifTibetan"),
    _entry("GeneralPunctuation", 0x2000, 0x206F, "Punctuation", None),
    _entry("LetterlikeSymbols", 0x2100, 0x214F, "Symbols", "NotoSansSymbols"),
    _entry("Hiragana", 0x3040, 0x309F, "Japanese", "NotoSansJP"),
    _entry("Katakana", 0x30A0, 0x30FF, "Japanese", "NotoSansJP"),
    _entry("CJKUnifiedIdeographs", 0x4E00, 0x9FFF, "Chinese", "NotoSansSC"),
    _entry("Emoticons", 0x1F300, 0x1FAFF, "Emoji", "NotoColorEmoji"),
)


@pytest.fixture
def fake_script_detector() -> ScriptDetector:
    """A :class:`ScriptDetector` over :data:`FAKE_SCRIPT_INDEX` (no font metadata, no network)."""
    detector = ScriptDetector()
    detector._lookup = FallbackLookup(FallbackIndex(list(FAKE_SCRIPT_INDEX)))
    return detector


__all__ = ["FAKE_SCRIPT_INDEX", "FIXTURES", "FakeConverter", "FakeFetch", "Harness", "field"]
