"""The ``glossary`` pass: front-matter acronym entries → ``AbbrDef`` records.

Decision X5 (``specs/migration/decisions.md``) expected no pass here: tmark
emits ``Abbr`` from ``press.declare.acronyms`` and ``*[X]: …``, and TeXSmith's
structured ``glossary:`` section (``style``, ``groups``, ``entries``) was to be
read by the ``ts-glossary`` fragment alone. The verification the decision asked
for (``examples/glossary``, ``examples/abbr``) failed — parity triage F2 — so
the pass exists after all, as the IR twin of the legacy
``glossary.append_synthetic_abbr_lines``.

What fails without it: the deprecated top-level ``glossary:`` key is hoisted
whole into ``press.declare.glossary``, where tmark reads a *flat* ``term →
definition`` mapping. So ``style``, ``groups`` and ``entries`` become three
glossary "terms" (``\\newacronym{style}{style}{long}``), the real acronyms
under ``entries`` are never declared, and no occurrence of ``API`` in the prose
is substituted — the writer's ``abbr::keys`` only knows ``Document.
abbreviations`` and ``declare.acronyms``.

The pass therefore, before ``tmark.resolve``:

* validates the structured section with
  :func:`~texsmith.core.glossary.parse_front_matter_glossary` (an invalid one
  is reported as ``glossary-invalid`` and left alone, never raised);
* appends one :class:`~texsmith.ir.model.AbbrDef` per entry to
  ``Document.abbreviations`` — ``long`` before ``description``, as the legacy
  synthetic ``*[KEY]: …`` line used — so both writers substitute the key in the
  prose (``\\tsacr{KEY}`` / ``#ts-acr("KEY")``) and both backmatters list it; an
  inline ``*[KEY]: …`` definition of the same key wins, as it did when the
  synthetic lines were appended after the body;
* replaces ``press.declare.glossary`` with the terms it does *not* consume
  (a plain ``term: definition`` mapping written there directly), so the
  structured keys stop reaching ``Resolved.glossary``.

``glossary.groups``/``glossary.style`` keep flowing to the template context
through ``wrap_template_document``; only the acronym substitution is the IR's
business.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from texsmith.ir import model
from texsmith.passes import PassContext, diagnostic_span, spec


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

    from texsmith.core.documents import Document


__all__ = ["STRUCTURED_KEYS", "run"]

#: The keys that make a ``glossary:`` mapping TeXSmith's structured form
#: rather than tmark's flat ``term: definition`` one.
STRUCTURED_KEYS = frozenset({"entries", "groups", "style"})


def _leftover_terms(section: Mapping[str, Any]) -> dict[str, Any] | None:
    """The flat ``term: definition`` pairs of ``section``, structured keys removed."""
    terms = {key: value for key, value in section.items() if key not in STRUCTURED_KEYS}
    return terms or None


@spec("glossary", after=("include",), stage="pre")
def run(document: Document, ctx: PassContext) -> Document:
    from texsmith.core.glossary import GlossaryValidationError, parse_front_matter_glossary

    ir = document.ir
    if ir is None:
        return document
    declare = ir.front_matter.keys.press.declare
    section = declare.glossary
    if not isinstance(section, dict) or not (STRUCTURED_KEYS & set(section)):
        return document

    try:
        parsed = parse_front_matter_glossary({"glossary": section})
    except GlossaryValidationError as exc:
        ctx.diagnostics.emit("glossary-invalid", diagnostic_span(ir.front_matter.span), str(exc))
        return document
    if parsed is None:
        return document

    known = {definition.key.strip() for definition in ir.abbreviations}
    span = ir.front_matter.span
    added: list[model.AbbrDef] = []
    for entry in parsed.entries:
        key = entry.key.strip()
        expansion = " ".join((entry.long or entry.description).split())
        if not key or not expansion or key in known:
            continue
        known.add(key)
        added.append(model.AbbrDef(expansion=expansion, key=key, id=ctx.ids.next(), span=span))

    leftover = _leftover_terms(section)
    if not added and leftover == section:
        return document
    front_matter = replace(
        ir.front_matter,
        keys=replace(
            ir.front_matter.keys,
            press=replace(
                ir.front_matter.keys.press,
                declare=replace(declare, glossary=leftover),
            ),
        ),
    )
    return document.evolve(
        ir=replace(
            ir,
            abbreviations=(*ir.abbreviations, *added),
            front_matter=front_matter,
        )
    )
