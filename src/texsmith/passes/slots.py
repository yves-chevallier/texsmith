"""The ``slots`` pass: split the block list into template slot bodies.

``python-ir-and-passes.md`` §4, decision X11. Selector grammar from
``parse_slot_mapping``: ``#id`` matches ``Header.attrs.id``, bare text
matches the trimmed ``plain_text`` of a header (an id match is tried first,
as before), ``@document`` / ``*`` take the whole document. Anything else
(``.class``, ``div > h2``, attribute selectors) emits
``slot-selector-unsupported`` and the content stays in the default slot.
Only **top-level** headers are candidates; a match inside a container emits
``slot-nested-heading``.

Algorithm: wildcard slots take the whole block
list (and the default slot then receives nothing); each requested slot, in
request order, claims the first unclaimed top-level header by id then by
text (none → ``slot-missing``); a section is the header plus the following
top-level blocks up to the next header of a level ``<=`` its own; claimed
sections leave the block list and the remainder is the default slot.
``strip_heading`` (manifest) or ``flatten`` (front matter) drop the header.
Every body records its heading levels in document order, descending into
containers as ``_heading_levels_for_nodes`` did.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from texsmith.core.conversion.inputs import DOCUMENT_SELECTOR_SENTINEL, SlotOptions
from texsmith.diagnostics import NO_SPAN
from texsmith.ir import model
from texsmith.ir.walk import plain_text, walk
from texsmith.passes import PassContext, diagnostic_span, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["SlotBody", "heading_levels", "run", "split_slots"]

_WILDCARDS = frozenset({DOCUMENT_SELECTOR_SENTINEL.lower(), "*"})
_UNSUPPORTED = re.compile(r"^\.|[\[\]>+~]")


@dataclass(slots=True, frozen=True)
class SlotBody:
    """The blocks of one template slot and what the writer needs to know about them."""

    name: str
    blocks: tuple[model.Block, ...]
    position: int
    heading_levels: tuple[int, ...] = ()
    #: ``WriterOptions.headings.base_level`` for this body (the ``headings`` pass).
    base_level: int = 1
    numbered: bool = True
    #: The full-document slots (``@document``); the default slot is then empty.
    whole_document: bool = False


def heading_levels(blocks: tuple[model.Block, ...]) -> tuple[int, ...]:
    """The levels of every header in ``blocks``, nested ones included, in order."""
    return tuple(
        node.level for block in blocks for node in walk(block) if isinstance(node, model.Header)
    )


def _header_id(header: model.Header) -> str | None:
    return header.attrs.id


def _header_text(header: model.Header) -> str:
    return plain_text(header.content).strip()


def _section_end(blocks: tuple[model.Block, ...], start: int) -> int:
    header = blocks[start]
    assert isinstance(header, model.Header)
    end = start + 1
    while end < len(blocks):
        candidate = blocks[end]
        if isinstance(candidate, model.Header) and candidate.level <= header.level:
            break
        end += 1
    return end


def _match(
    blocks: tuple[model.Block, ...],
    selector: str,
    claimed: set[int],
) -> int | None:
    """Index of the first unclaimed top-level header matching ``selector``."""
    token = selector.strip()
    label = token[1:] if token.startswith("#") else token
    for index, block in enumerate(blocks):
        if index in claimed or not isinstance(block, model.Header):
            continue
        if label and _header_id(block) == label:
            return index
    if token.startswith("#"):
        return None
    for index, block in enumerate(blocks):
        if index in claimed or not isinstance(block, model.Header):
            continue
        if _header_text(block) == token:
            return index
    return None


def _nested_match(ir_document: model.Document, selector: str) -> model.Header | None:
    """A header matching ``selector`` inside a container (reported, never claimed)."""
    token = selector.strip()
    label = token[1:] if token.startswith("#") else token
    for block in ir_document.blocks:
        if isinstance(block, model.Header):
            continue
        for node in walk(block):
            if not isinstance(node, model.Header):
                continue
            if (label and _header_id(node) == label) or (
                not token.startswith("#") and _header_text(node) == token
            ):
                return node
    return None


def split_slots(
    ir_document: model.Document,
    requests: dict[str, str],
    default_slot: str,
    *,
    strip_heading: frozenset[str] = frozenset(),
    slot_options: dict[str, SlotOptions] | None = None,
    ctx: PassContext | None = None,
) -> tuple[SlotBody, ...]:
    """Split ``ir_document.blocks`` into bodies; diagnostics go to ``ctx`` when given."""
    options = dict(slot_options or {})
    blocks = ir_document.blocks
    front_span = (
        diagnostic_span(ir_document.front_matter.span) if ir_document.front_matter.raw else NO_SPAN
    )

    def emit(code: str, span: object, message: str) -> None:
        if ctx is not None:
            ctx.diagnostics.emit(code, span, message)  # type: ignore[arg-type]

    wildcard: list[str] = []
    selected: dict[str, str] = {}
    for slot_name, selector in requests.items():
        token = (selector or "").strip()
        if not token:
            continue
        if token.lower() in _WILDCARDS:
            wildcard.append(slot_name)
        elif _UNSUPPORTED.search(token):
            emit(
                "slot-selector-unsupported",
                front_span,
                f"slot '{slot_name}': selector '{token}' is not a heading id or title; "
                "content stays in the default slot",
            )
        else:
            selected[slot_name] = token

    claimed: set[int] = set()
    matched: dict[str, int] = {}
    for slot_name, selector in selected.items():
        index = _match(blocks, selector, claimed)
        if index is None:
            nested = _nested_match(ir_document, selector)
            if nested is not None:
                emit(
                    "slot-nested-heading",
                    diagnostic_span(nested.span),
                    f"slot '{slot_name}': heading '{selector}' is nested in a container; "
                    "only top-level headings form a slot",
                )
            else:
                emit(
                    "slot-missing",
                    front_span,
                    f"unable to locate section '{selector}' for slot '{slot_name}'",
                )
            continue
        for cursor in range(index, _section_end(blocks, index)):
            claimed.add(cursor)
        matched[slot_name] = index

    bodies: list[SlotBody] = []
    for offset, slot_name in enumerate(wildcard):
        bodies.append(
            SlotBody(
                name=slot_name,
                blocks=blocks,
                position=-(len(wildcard) - offset),
                heading_levels=heading_levels(blocks),
                whole_document=True,
            )
        )

    for slot_name, index in sorted(matched.items(), key=lambda item: item[1]):
        end = _section_end(blocks, index)
        section = blocks[index:end]
        flatten = options.get(slot_name, SlotOptions()).flatten
        if (slot_name in strip_heading or flatten) and section:
            section = section[1:]
        bodies.append(
            SlotBody(
                name=slot_name,
                blocks=section,
                position=index,
                heading_levels=heading_levels(section),
            )
        )

    remainder: tuple[model.Block, ...] = ()
    if not wildcard:
        remainder = tuple(block for cursor, block in enumerate(blocks) if cursor not in claimed)
    position = max((body.position for body in bodies), default=-1) + 1
    bodies.append(
        SlotBody(
            name=default_slot,
            blocks=remainder,
            position=position,
            heading_levels=heading_levels(remainder),
        )
    )
    bodies.sort(key=lambda body: body.position)
    return tuple(bodies)


@spec("slots", stage="post")
def run(document: Document, ctx: PassContext) -> Document:
    if document.ir is None:
        return document
    template = ctx.template
    bodies = split_slots(
        document.ir,
        dict(template.requests),
        template.default_slot,
        strip_heading=template.strip_heading,
        slot_options=document.slot_options,
        ctx=ctx,
    )
    return document.evolve(bodies=bodies)
