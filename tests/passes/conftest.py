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

from texsmith.adapters.markdown import split_front_matter
from texsmith.core.conversion.inputs import InputKind, SlotOptions
from texsmith.core.documents import Document, TitleStrategy
from texsmith.diagnostics import DiagnosticSink, FileTable
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


__all__ = ["FIXTURES", "Harness", "field"]
