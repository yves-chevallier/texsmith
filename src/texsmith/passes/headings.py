"""The ``headings`` pass: per-body heading options for the writer (decision X1).

``Header.level`` stays the author's. For every body the pass computes what
``core.py`` used to feed the legacy writer as ``runtime["base_level"]`` and
``runtime["numbered"]``:

* ``offset = 1 - min(heading_levels)`` (``0`` when the body has no heading;
  the promoted title is already gone from the default slot, so its level is
  skipped as before);
* ``base_level = slot_level + document.base_level + offset``, where
  ``slot_level`` is the template's level for the slot
  (``TemplateBinding.slot_levels()``) — the writer renders
  ``Header.level + base_level - 1``, the legacy rule;
* ``numbered`` is the document's flag (front matter ``numbered``), off for the
  ``preface`` slot.

The values travel on :class:`~texsmith.passes.slots.SlotBody` and become
``WriterOptions.headings`` of the ``tmark.write`` call for that body.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from texsmith.passes import PassContext, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


def body_offset(levels: tuple[int, ...]) -> int:
    """``1 - min(levels)``, ``0`` for a body without headings."""
    return 1 - min(levels) if levels else 0


@spec("headings", after=("slots",), stage="post")
def run(document: Document, ctx: PassContext) -> Document:
    if not document.bodies:
        return document
    template = ctx.template
    updated = []
    for body in document.bodies:
        slot_level = template.levels.get(body.name, template.base_level)
        base_level = slot_level + document.base_level + body_offset(body.heading_levels)
        numbered = document.numbered and body.name != "preface"
        updated.append(replace(body, base_level=base_level, numbered=numbered))
    return document.evolve(bodies=tuple(updated))
