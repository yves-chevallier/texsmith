"""The tmark reader: TMark text → ``tmark.parse`` → :mod:`texsmith.ir.model`.

The parser lives in the ``tmark`` wheel; this module is the thin seam that
turns its JSON into the generated models (:func:`texsmith.ir.codec.decode_document`)
and its parse diagnostics into :class:`~texsmith.diagnostics.Diagnostic`
records with ``origin="tmark"``. Parsing never fails: a malformed text is a
document plus diagnostics (``specs/migration/python-ir-and-passes.md`` §2).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import tmark

from texsmith.diagnostics import Diagnostic, from_tmark
from texsmith.ir import codec, model


__all__ = ["ReadResult", "parse_payload", "read"]

ReadResult = tuple[model.Document, list[Diagnostic]]


def parse_payload(
    text: str, *, file_id: int = 0, name: str = "<memory>", profile: str = "default"
) -> dict[str, Any]:
    """The raw ``tmark.parse`` JSON of ``text`` (root ``tmark`` and ``diagnostics`` included)."""
    return tmark.parse(text, file=name, file_id=file_id, profile=profile)


def read(
    text: str, *, file_id: int = 0, name: str = "<memory>", profile: str = "default"
) -> ReadResult:
    """Parse ``text`` into the IR models and the parse diagnostics.

    ``file_id`` is the id every span of the document carries (the position of
    the file in the build's :class:`~texsmith.diagnostics.FileTable`); ``name``
    is what tmark prints in its own messages.
    """
    payload = parse_payload(text, file_id=file_id, name=name, profile=profile)
    document = codec.decode_document(payload)
    return document, diagnostics_of(payload)


def diagnostics_of(payload: Mapping[str, Any]) -> list[Diagnostic]:
    """The ``diagnostics`` of a tmark result as records with ``origin="tmark"``."""
    records = payload.get("diagnostics") or ()
    return [from_tmark(record) for record in records]
