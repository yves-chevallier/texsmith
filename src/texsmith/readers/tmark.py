"""The tmark reader: TMark text → ``tmark.parse`` → :mod:`tmark.ir.model`.

The parser lives in the ``tmark`` wheel; this module is the thin seam that
turns its JSON into the generated models (:func:`tmark.ir.codec.decode_document`)
and its parse diagnostics into :class:`~texsmith.diagnostics.Diagnostic`
records with ``origin="tmark"``. Parsing never fails: a malformed text is a
document plus diagnostics (``specs/migration/python-ir-and-passes.md`` §2).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import tmark
from tmark.ir import codec, model

from texsmith.diagnostics import Diagnostic, from_tmark


__all__ = ["ReadResult", "decode", "parse_payload", "read"]

ReadResult = tuple[model.Document, list[Diagnostic]]

_wheel_schema_checked = False


def _ensure_wheel_schema() -> None:
    """Raise once if the installed ``tmark`` wheel ships an IR schema ``tmark.ir.model``
    was not generated against.

    Checked here, the seam where TeXSmith first asks the wheel to parse a
    document: a silently mismatched schema would surface later as a
    confusing ``decode_document`` failure (an unknown field, or a missing
    one) far from its cause. ``wheel_schema_mismatch`` itself already names
    both hashes and versions.
    """
    global _wheel_schema_checked
    if _wheel_schema_checked:
        return
    _wheel_schema_checked = True
    mismatch = codec.wheel_schema_mismatch()
    if mismatch is not None:
        raise RuntimeError(mismatch)


def parse_payload(
    text: str, *, file_id: int = 0, name: str = "<memory>", profile: str = "default"
) -> dict[str, Any]:
    """The raw ``tmark.parse`` JSON of ``text`` (root ``tmark`` and ``diagnostics`` included)."""
    _ensure_wheel_schema()
    return tmark.parse(text, file=name, file_id=file_id, profile=profile)


def read(
    text: str, *, file_id: int = 0, name: str = "<memory>", profile: str = "default"
) -> ReadResult:
    """Parse ``text`` into the IR models and the parse diagnostics.

    ``file_id`` is the id every span of the document carries (the position of
    the file in the build's :class:`~texsmith.diagnostics.FileTable`); ``name``
    is what tmark prints in its own messages.
    """
    return decode(parse_payload(text, file_id=file_id, name=name, profile=profile))


def decode(payload: Mapping[str, Any]) -> ReadResult:
    """A raw ``tmark.parse`` result as the IR models and the parse diagnostics.

    The seam a caller that had to touch the payload comes back through: the
    site's book moves every span onto the file the bytes came from before the
    document is typed (:func:`~texsmith.site.index.parse_page`).
    """
    return codec.decode_document(payload), diagnostics_of(payload)


def diagnostics_of(payload: Mapping[str, Any]) -> list[Diagnostic]:
    """The ``diagnostics`` of a tmark result as records with ``origin="tmark"``."""
    records = payload.get("diagnostics") or ()
    return [from_tmark(record) for record in records]
