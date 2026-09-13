"""What a document's front matter says about the run that renders it.

A handful of decisions have two sources: a command-line flag and a front-matter
key the document carries into every build. The rule is the same for all of
them — the explicit flag wins, the front matter answers otherwise, and an
unusable value falls back to the default — and it belongs to neither the CLI
(which would then own a reading of ``press``) nor the render (which never sees
a flag).

``press.features`` is a boolean map in tmark's front-matter schema, which is
why the three-valued ``deprecated`` switch lives under ``press.diagnostics``
instead.
"""

from __future__ import annotations

from collections.abc import Mapping
import contextlib
from dataclasses import replace
from typing import Any

from texsmith.core.coerce import coerce_bool
from texsmith.core.metadata import PressMetadataError, normalise_press_metadata
from texsmith.diagnostics import Diagnostic, Severity


#: tmark's records for legacy spellings the ``tmark lint --fix`` rewrite removes.
DEPRECATED_CODES: frozenset[str] = frozenset({"deprecated", "deprecated-frontmatter-key"})

#: ``--deprecated`` / ``press.diagnostics.deprecated``: how those records are reported.
DEPRECATED_LEVELS: tuple[str, ...] = ("warning", "info", "off")


def lookup_bool(mapping: Mapping[str, Any] | None, path: tuple[str, ...]) -> bool | None:
    """The boolean-like value at ``path``, ``None`` when the path is absent."""
    if not isinstance(mapping, Mapping):
        return None
    cursor: Any = mapping
    for key in path:
        if not isinstance(cursor, Mapping) or key not in cursor:
            return None
        cursor = cursor[key]
    return coerce_bool(cursor)


def deprecated_level(front_matter: Mapping[str, Any] | None, explicit: str | None = None) -> str:
    """The level the deprecation records are reported at (``warning`` by default).

    ``explicit`` is the CLI's ``--deprecated``; without it the front matter's
    ``press.diagnostics.deprecated`` decides. An unknown value is the default.
    """
    for candidate in (explicit, _lookup_deprecated(front_matter)):
        if isinstance(candidate, str) and candidate.strip().lower() in DEPRECATED_LEVELS:
            return candidate.strip().lower()
    return "warning"


def _lookup_deprecated(front_matter: Mapping[str, Any] | None) -> str | None:
    if not isinstance(front_matter, Mapping):
        return None
    press = front_matter.get("press")
    section = press.get("diagnostics") if isinstance(press, Mapping) else None
    if section is None:
        section = front_matter.get("diagnostics")
    if not isinstance(section, Mapping):
        return None
    value = section.get("deprecated")
    if isinstance(value, bool):
        return "warning" if value else "off"
    return value if isinstance(value, str) else None


def demote_deprecated(record: Diagnostic, level: str) -> Diagnostic | None:
    """``record`` as ``level`` reports it: unchanged, lowered to ``info`` or dropped (``None``).

    Only the :data:`DEPRECATED_CODES` are touched; every other record passes
    as is, whatever the level. Applied before the ``--strict`` check, so the
    legacy spellings the examples still carry do not fail a strict run.
    """
    if record.code not in DEPRECATED_CODES or level == "warning":
        return record
    if level == "off":
        return None
    if record.severity <= Severity.INFO:
        return record
    return replace(record, severity=Severity.INFO)


def strict_enabled(front_matter: Mapping[str, Any] | None, explicit: bool = False) -> bool:
    """Whether a recorded warning or error should fail the run.

    ``--strict`` turns it on; ``press.features.strict`` turns it on for a
    document that must carry the setting into every build. Neither can turn
    the other off — a document asking to be strict is asking for the whole
    run, and there is no ``--no-strict`` for it to lose to.
    """
    return bool(explicit) or bool(lookup_bool(front_matter, ("press", "features", "strict")))


def declared_template(front_matter: Mapping[str, Any] | None) -> str | None:
    """The template the front matter selects (``press.template``), if any.

    The mapping is normalised first, so the deprecated root spelling is read
    exactly as a conversion would read it; a malformed ``press`` section names
    no template rather than raising, because the caller reports it separately.
    """
    if not isinstance(front_matter, Mapping):
        return None
    payload = dict(front_matter)
    with contextlib.suppress(PressMetadataError):
        normalise_press_metadata(payload)
    value = payload.get("template")
    if isinstance(value, str) and (candidate := value.strip()):
        return candidate
    return None


def numbered_setting(
    front_matter: Mapping[str, Any] | None,
    template_options: Mapping[str, Any] | None = None,
    *,
    default: bool = True,
) -> bool:
    """Whether the document's headings are numbered.

    The front matter's ``numbered`` answers first and a ``--attribute
    numbered=…`` overrides it, because an attribute is typed for this run
    while the front matter belongs to the document.
    """
    resolved = default
    for source in (front_matter, template_options):
        value = lookup_bool(source, ("numbered",))
        if value is not None:
            resolved = value
    return resolved


__all__ = [
    "DEPRECATED_CODES",
    "DEPRECATED_LEVELS",
    "declared_template",
    "demote_deprecated",
    "deprecated_level",
    "lookup_bool",
    "numbered_setting",
    "strict_enabled",
]
