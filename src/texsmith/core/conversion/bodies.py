"""``tmark.write`` on the Python side: bodies, ``Requires`` and ``WriterOptions``.

``writers-and-passes.md`` §1 (Body/Requires as Python sees them) and
``python-ir-and-passes.md`` §4: one ``write`` call per slot body, each
receiving the full document with ``blocks`` replaced by the body's slice (the
footnotes and abbreviations stay), the shared ``Resolved`` handle, and the
``WriterOptions`` derived from the template context plus the per-body
heading options of the ``headings`` pass. Python unions the ``Requires`` of
every body; :mod:`texsmith.core.fragments.activation` turns the union into
fragment activation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import tmark
from tmark.ir import codec, model

from texsmith.core.code_options import normalise_inline_options
from texsmith.diagnostics import DiagnosticSink

from .resolution import ResolveOptions


if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


__all__ = ["Body", "Requires", "build_writer_options", "write_body"]

_CODE_ENGINES = ("pygments", "minted", "listings", "verbatim")


@dataclass(slots=True)
class Requires:
    """What the bodies need from the template (``tmark_writers::Requires``)."""

    packages: list[str] = field(default_factory=list)
    fragments: list[str] = field(default_factory=list)
    shell_escape: bool = False
    assets: list[dict[str, Any]] = field(default_factory=list)
    bibliography: bool = False
    #: Cited keys, first seen first.
    citations: list[str] = field(default_factory=list)
    #: ``\tsacr{key}`` keys emitted, first seen first.
    acronyms: list[str] = field(default_factory=list)
    #: Index registries used; ``""`` is the default registry.
    index: list[str] = field(default_factory=list)
    #: TMark-numbered series used.
    counters: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, payload: Mapping[str, Any] | None) -> Requires:
        data = dict(payload or {})
        return cls(
            packages=_strings(data.get("packages")),
            fragments=_strings(data.get("fragments")),
            shell_escape=bool(data.get("shell_escape", False)),
            assets=[dict(item) for item in data.get("assets") or () if isinstance(item, Mapping)],
            bibliography=bool(data.get("bibliography", False)),
            citations=_strings(data.get("citations")),
            acronyms=_strings(data.get("acronyms")),
            index=_strings(data.get("index")),
            counters=_strings(data.get("counters")),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "packages": list(self.packages),
            "fragments": list(self.fragments),
            "shell_escape": self.shell_escape,
            "assets": [dict(item) for item in self.assets],
            "bibliography": self.bibliography,
            "citations": list(self.citations),
            "acronyms": list(self.acronyms),
            "index": list(self.index),
            "counters": list(self.counters),
        }

    def merge(self, other: Requires) -> None:
        """Union ``other`` into this record, keeping first-seen order of the lists."""
        _extend(self.packages, other.packages)
        _extend(self.fragments, other.fragments)
        self.shell_escape = self.shell_escape or other.shell_escape
        self.assets.extend(item for item in other.assets if item not in self.assets)
        self.bibliography = self.bibliography or other.bibliography
        _extend(self.citations, other.citations)
        _extend(self.acronyms, other.acronyms)
        _extend(self.index, other.index)
        _extend(self.counters, other.counters)

    @classmethod
    def union(cls, records: Iterable[Requires]) -> Requires:
        total = cls()
        for record in records:
            total.merge(record)
        return total


def _strings(value: Any) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


def _extend(target: list[str], values: Iterable[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


@dataclass(slots=True)
class Body:
    """One ``tmark.write`` result."""

    text: str
    #: ``(start, end, node_id)`` over the output bytes; empty unless ``source_map``.
    map: list[tuple[int, int, int]] = field(default_factory=list)
    requires: Requires = field(default_factory=Requires)

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Body:
        entries = payload.get("map") or ()
        return cls(
            text=str(payload.get("text", "")),
            map=[(int(a), int(b), int(c)) for a, b, c in entries],
            requires=Requires.from_json(payload.get("requires")),
        )


def build_writer_options(
    *,
    backend: str,
    language: str | None = None,
    code_options: Mapping[str, Any] | None = None,
    legacy_accents: bool = False,
    media: str | None = None,
    base_level: int = 1,
    numbered: bool = True,
    refs: Mapping[str, str] | None = None,
    numbering: Mapping[str, str] | None = None,
    source_map: bool = False,
) -> dict[str, Any]:
    """The ``options`` dict of ``tmark.write``, one key per ``WriterOptions`` field.

    ``code_options`` is the merged ``code`` section of the template context
    (``_resolve_code_options``): ``engine``, ``inline.plain``, ``inline.breaks``.
    """
    code = dict(code_options or {})
    engine = str(code.get("engine") or "pygments").strip().lower()
    if engine not in _CODE_ENGINES:
        engine = "pygments"
    inline = normalise_inline_options(code.get("inline"))
    options: dict[str, Any] = {
        "media": media or ("web" if backend == "html" else "print"),
        "code": {
            "engine": engine,
            "inline_plain": bool(inline["plain"]),
            "inline_breaks": str(inline["breaks"]),
        },
        "latex": {"legacy_accents": bool(legacy_accents)},
        "headings": {"base_level": int(base_level), "numbered": bool(numbered)},
        "source_map": bool(source_map),
    }
    if language:
        options["lang"] = language
    if refs:
        options["refs"] = {key: str(value) for key, value in refs.items()}
    if numbering:
        options["numbering"] = {key: str(value) for key, value in numbering.items()}
    return options


def write_body(
    ir_document: model.Document,
    backend: str,
    options: Mapping[str, Any],
    *,
    blocks: tuple[model.Block, ...] | None = None,
    loader: Any = None,
    resolved: Any = None,
    resolve_options: ResolveOptions | None = None,
    sink: DiagnosticSink | None = None,
) -> Body:
    """Write ``ir_document`` (or the slice ``blocks`` of it) with ``backend``.

    ``resolved`` is the ``tmark.resolve`` result (or its ``handle``) shared by
    every body of the document; without it tmark resolves the slice itself
    through ``loader`` with ``resolve_options``.
    """
    target = ir_document if blocks is None else replace(ir_document, blocks=blocks)
    payload = codec.encode_document(target)
    payload["tmark"] = tmark.version()
    handle = resolved.get("handle", resolved) if isinstance(resolved, Mapping) else resolved
    result = tmark.write(
        payload,
        backend,
        dict(options),
        loader,
        handle,
        resolve_options.to_json() if resolve_options is not None else None,
    )
    if sink is not None:
        sink.extend_from_tmark(result.get("diagnostics") or ())
    return Body.from_json(result)
