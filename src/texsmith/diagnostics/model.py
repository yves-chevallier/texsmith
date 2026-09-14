"""The one diagnostic record TeXSmith and tmark share.

The shape is the JSON of ``tmark_ir::Diagnostic`` (``specs/migration/
python-ir-and-passes.md`` §6) plus ``origin``: ``code`` is a string because
Rust's ``Code`` is a closed enum and TeXSmith adds its own identifiers
(:mod:`texsmith.diagnostics.codes`).

``Span`` and ``NO_SPAN`` come from ``tmark.ir.model``, generated from the
schema that defines them ("Byte span as [file, start, end]"). They used to be
declared here and imported by the IR models, which meant a Python restatement
of a Rust type kept in step by hand. ``Fix`` is TeXSmith's and stays.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from tmark.ir.model import NO_SPAN, Span


class Severity(str, Enum):
    """tmark's four severities, ordered from the mildest to the worst.

    The four comparisons are spelled out: ``str`` already defines them
    (alphabetically, which puts ``info`` above ``error``), so a partial
    definition would be silently completed by the string ones.
    """

    HINT = "hint"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        """Position in the ``hint < info < warning < error`` order."""
        return _SEVERITY_ORDER.index(self)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank

    def __hash__(self) -> int:
        return hash(self.value)


_SEVERITY_ORDER = (Severity.HINT, Severity.INFO, Severity.WARNING, Severity.ERROR)


@dataclass(frozen=True, slots=True)
class Fix:
    """A text edit an editor can apply: replace ``span`` with ``replacement``."""

    span: Span
    replacement: str

    def to_json(self) -> dict[str, Any]:
        return {"span": self.span.to_json(), "replacement": self.replacement}

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Fix:
        return cls(Span.from_json(payload["span"]), str(payload["replacement"]))


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One finding, from a Python pass or from the tmark bindings."""

    code: str
    severity: Severity
    span: Span
    #: One sentence, no trailing period, names the construct.
    message: str
    fix: Fix | None = None
    #: Other locations involved, each with a label (the other definition of a
    #: duplicate key).
    related: tuple[tuple[Span, str], ...] = ()
    #: ``"texsmith"`` for Python records, ``"tmark"`` for parse/resolve/lint/write records.
    origin: str = "texsmith"

    @property
    def key(self) -> tuple[str, Span, str]:
        """The identity the sink deduplicates on."""
        return (self.code, self.span, self.message)

    def to_json(self) -> dict[str, Any]:
        """Tmark's JSON shape plus ``origin``; ``fix`` and ``related`` only when set."""
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "span": self.span.to_json(),
            "message": self.message,
        }
        if self.fix is not None:
            payload["fix"] = self.fix.to_json()
        if self.related:
            payload["related"] = [[span.to_json(), label] for span, label in self.related]
        payload["origin"] = self.origin
        return payload


def from_tmark(record: Mapping[str, Any]) -> Diagnostic:
    """Build a :class:`Diagnostic` from a record returned by the tmark bindings.

    The record is the ``serde`` JSON of ``tmark_ir::Diagnostic``: ``fix`` and
    ``related`` are absent when empty. ``origin`` is forced to ``"tmark"``.
    """
    fix_payload = record.get("fix")
    related_payload = record.get("related") or ()
    return Diagnostic(
        code=str(record["code"]),
        severity=Severity(str(record["severity"])),
        span=Span.from_json(record["span"]),
        message=str(record["message"]),
        fix=Fix.from_json(fix_payload) if fix_payload is not None else None,
        related=tuple((Span.from_json(span), str(label)) for span, label in related_payload),
        origin="tmark",
    )


__all__ = ["NO_SPAN", "Diagnostic", "Fix", "Severity", "Span", "from_tmark"]
