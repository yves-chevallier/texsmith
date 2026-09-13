"""The ``scripts`` pass: foreign-script text runs → ``Span{script}``, and the font summary.

``writers-and-passes.md`` §3 row 9 and the R4 decision. Runs after ``var``
and ``emoji`` (a moustache value is text too; an emoji span is fenced off so
a cluster is never classified as a script run), before ``resolve``.

Every :class:`~texsmith.ir.model.Str` is segmented with the legacy
:class:`~texsmith.fonts.scripts.ScriptDetector` rules (``fonts/scripts.py``):
a character's Unicode block maps to a script group through the
Noto/ucharclasses fallback index; a run whose group is not one of
``latin``, ``common``, ``punctuation``, ``other`` becomes
``Span{attrs: script=<slug>}`` around the text — the LaTeX writer renders
``\\tsscript{slug}{…}`` and names ``ts-fonts``. Combining marks and
diacritics join the current run, whitespace joins while inside a run, the
CJK groups take a majority vote per text run, and a chunk that is a single
Greek or Hebrew letter becomes ``Math{\\alpha}`` (the math glyph exists;
``scripts.py:89-113``). Code, math and raw nodes hold no ``Str`` and are
untouched; spans the ``emoji`` pass produced are skipped.

The per-document font summary replaces the whole-body scan of the rendered
LaTeX (``core/conversion/renderer.py``, ``_scan_fallback`` over the slot
text) on the tmark path: one ``summary`` call over the text of the whole IR
(every ``Str``, ``Code``, ``Math``, ``Abbr``, ``CodeBlock`` and
``MathBlock``, all slots at once) gives ``fallback_summary``; merged with
the per-run usage records it gives ``script_usage`` (slug, group, font,
count). Both are handed back as ``ctx.values`` and reach the ``fonts``
context keys the ``ts-fonts`` fragment and ``fonts/provisioning.py`` read.

**Intended difference with the legacy wrapper.** ``LaTeXWriter._script_wrap_block``
ran on the rendered LaTeX and wrapped nothing in a paragraph whose source
held a backslash or a math payload (``writer.py:198-209``, ``:637-639``), so
a Cyrillic word next to an ``\\emph`` or a ``$x$`` got no ``\\textcyrillic``;
the pass sees ``Str`` nodes, so those runs are wrapped too. The parity
harness records this as an intended difference.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from texsmith.diagnostics import NO_SPAN
from texsmith.fonts.cache import FontCache
from texsmith.fonts.fallback import merge_fallback_summaries
from texsmith.fonts.scripts import (
    _MATH_LETTER_GROUPS,
    _MATH_LETTER_MAP,
    ScriptDetector,
    ScriptSpec,
    _slugify,
    fallback_summary_to_usage,
    merge_script_usage,
)
from texsmith.ir import model
from texsmith.ir.walk import map_inlines, walk
from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document
    from texsmith.fonts.fallback import FallbackEntry


__all__ = ["document_text", "run", "script_detector"]

DETECTOR_KEY = "script_detector"

_TEXT_NODES = (
    model.Str,
    model.Code,
    model.Math,
    model.Abbr,
    model.CodeBlock,
    model.MathBlock,
)


def script_detector(ctx: PassContext) -> ScriptDetector:
    """The detector of this build (``ctx.values["script_detector"]``, a test may inject one)."""
    detector = ctx.values.get(DETECTOR_KEY)
    if not isinstance(detector, ScriptDetector):
        detector = ScriptDetector(cache=FontCache())
        ctx.values[DETECTOR_KEY] = detector
    return detector


def document_text(ir_document: model.Document) -> str:
    """The text of every text-bearing node of the document, space-separated."""
    parts = [node.text for node in walk(ir_document) if isinstance(node, _TEXT_NODES)]
    return " ".join(part for part in parts if part)


def _math_letter(chunk: str, group: str | None) -> tuple[str, str, str] | None:
    """``(prefix, macro, suffix)`` for a chunk that is one Greek/Hebrew letter, else ``None``."""
    if group and group.lower() not in _MATH_LETTER_GROUPS:
        return None
    trimmed = chunk.strip()
    if len(trimmed) != 1:
        return None
    macro = _MATH_LETTER_MAP.get(trimmed)
    if macro is None:
        return None
    prefix = chunk[: len(chunk) - len(chunk.lstrip())]
    suffix = chunk[len(chunk.rstrip()) :]
    return prefix, macro, suffix


def _merge_strs(pieces: list[model.Inline]) -> list[model.Inline]:
    """Join consecutive ``Str`` pieces (a math letter's whitespace and the next chunk)."""
    merged: list[model.Inline] = []
    for item in pieces:
        last = merged[-1] if merged else None
        if isinstance(item, model.Str) and isinstance(last, model.Str):
            merged[-1] = replace(last, text=last.text + item.text)
            continue
        merged.append(item)
    return merged


def _is_fenced(node: model.Node) -> bool:
    if not isinstance(node, model.SpanNode):
        return False
    return any(key in {"emoji", "script"} for key, _ in node.attrs.kv)


@spec("scripts", after=("var", "emoji"), stage="pre", needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    if document.ir is None:
        return document
    detector = script_detector(ctx)
    specs: dict[str, ScriptSpec] = {}

    def record(group: str, entry: FallbackEntry | None, chunk: str) -> ScriptSpec:
        slug = _slugify(group)
        font_name = entry.font.get("name") if entry is not None and entry.font else None
        item = specs.get(slug)
        if item is None:
            item = ScriptSpec(
                group=group,
                slug=slug,
                font_name=font_name,
                font_command=f"{slug}font",
                text_command=f"text{slug}",
            )
            specs[slug] = item
        elif font_name and not item.font_name:
            item.font_name = font_name
        item.count += len(chunk)
        return item

    def piece(node: model.Str, text: str) -> model.Str:
        return model.Str(text=text, id=ctx.ids.next(), span=node.span)

    def visit(node: model.Inline) -> model.Inline | tuple[model.Inline, ...]:
        if not isinstance(node, model.Str) or not node.text or node.text.isascii():
            return node
        runs = detector._segment_text(node.text, include_whitespace=True)  # noqa: SLF001
        if all(group is None and _math_letter(chunk, None) is None for group, chunk, _ in runs):
            return node
        pieces: list[model.Inline] = []
        for group, chunk, entry in runs:
            letter = _math_letter(chunk, group)
            if letter is not None:
                prefix, macro, suffix = letter
                if prefix:
                    pieces.append(piece(node, prefix))
                pieces.append(model.Math(text=macro, id=ctx.ids.next(), span=node.span))
                if suffix:
                    pieces.append(piece(node, suffix))
                continue
            if group:
                item = record(group, entry, chunk)
                pieces.append(
                    model.SpanNode(
                        attrs=model.Attrs(kv=(("script", item.slug),)),
                        content=(piece(node, chunk),),
                        id=ctx.ids.next(),
                        span=node.span,
                    )
                )
                continue
            pieces.append(piece(node, chunk))
        merged = _merge_strs(pieces)
        if len(merged) == 1 and isinstance(merged[0], model.Str):
            return node
        return tuple(merged)

    rebuilt = map_inlines(document.ir, visit, skip=_is_fenced)

    usage = [item.to_mapping() for item in specs.values()]
    text = document_text(rebuilt)
    summary: list[dict] = []
    if text and not text.isascii():
        try:
            summary = detector._ensure_lookup().summary(text)  # noqa: SLF001
        except Exception as exc:
            ctx.diagnostics.emit(
                "font-scan-failed", NO_SPAN, f"the font coverage scan failed: {exc}"
            )
            summary = []
    if summary:
        usage = merge_script_usage(usage, fallback_summary_to_usage(summary))
        ctx.values["fallback_summary"] = merge_fallback_summaries(
            ctx.values.get("fallback_summary", []), summary
        )
    if usage:
        ctx.values["script_usage"] = merge_script_usage(ctx.values.get("script_usage", []), usage)

    if rebuilt is document.ir:
        return document
    return document.evolve(ir=rebuilt)
