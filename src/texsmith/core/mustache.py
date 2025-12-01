"""Utility helpers for resolving simple mustache-style placeholders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from .diagnostics import DiagnosticEmitter


_MUSTACHE_RE = re.compile(r"\{\{\s*([^\}\s][^\}]*)\s*\}\}")
_MISSING = object()


def _lookup(context: Mapping[str, Any] | None, path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current.get(part)
    return current


def _resolve_value(path: str, contexts: Sequence[Mapping[str, Any] | None]) -> Any:
    for context in contexts:
        value = _lookup(context, path)
        if value is not _MISSING:
            return value
    return _MISSING


def replace_mustaches(
    text: str,
    contexts: Sequence[Mapping[str, Any] | None],
    *,
    emitter: DiagnosticEmitter | None = None,
    source: str | None = None,
) -> str:
    """Replace ``{{path.to.value}}`` placeholders in ``text`` using ``contexts``."""

    def _warn(message: str) -> None:
        if emitter:
            emitter.warning(message)

    def _replacement(match: re.Match[str]) -> str:
        raw_path = match.group(1).strip()
        value = _resolve_value(raw_path, contexts)
        if value is _MISSING or value is None or (isinstance(value, str) and not value.strip()):
            location = f" in {source}" if source else ""
            _warn(f"Unresolved mustache '{{{{{raw_path}}}}}'{location}; leaving placeholder as-is.")
            return match.group(0)
        return str(value)

    return _MUSTACHE_RE.sub(_replacement, text)


def replace_mustaches_in_structure(
    payload: Any,
    contexts: Sequence[Mapping[str, Any] | None],
    *,
    emitter: DiagnosticEmitter | None = None,
    source: str | None = None,
) -> Any:
    """Recursively resolve mustache placeholders inside mappings/sequences/strings."""
    if isinstance(payload, str):
        return replace_mustaches(payload, contexts, emitter=emitter, source=source)
    if isinstance(payload, Mapping):
        return {
            key: replace_mustaches_in_structure(value, contexts, emitter=emitter, source=source)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [
            replace_mustaches_in_structure(item, contexts, emitter=emitter, source=source)
            for item in payload
        ]
    if isinstance(payload, tuple):
        return tuple(
            replace_mustaches_in_structure(item, contexts, emitter=emitter, source=source)
            for item in payload
        )
    return payload


__all__ = ["replace_mustaches", "replace_mustaches_in_structure"]
