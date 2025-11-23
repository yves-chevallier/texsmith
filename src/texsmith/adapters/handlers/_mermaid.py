"""Heuristics and helpers shared across handlers to detect Mermaid diagrams."""

from __future__ import annotations

import base64
import binascii
import json
from urllib.parse import urlparse
import zlib

from texsmith.core.exceptions import InvalidNodeError


MERMAID_FILE_SUFFIXES = (".mmd", ".mermaid")

MERMAID_KEYWORDS = {
    "graph",
    "flowchart",
    "sequencediagram",
    "classdiagram",
    "statediagram",
    "gantt",
    "erdiagram",
    "journey",
    "packet",
}


def looks_like_mermaid(diagram: str) -> bool:
    """Return True when the payload resembles a Mermaid diagram."""
    if not diagram:
        return False

    for line in diagram.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("%%"):
            continue
        token = stripped.split(maxsplit=1)[0].lower()
        return token in MERMAID_KEYWORDS

    return False


def _extract_mermaid_code(payload: str) -> str:
    """Return Mermaid code embedded in a Mermaid Live payload."""
    candidate = payload.lstrip()
    if not candidate.startswith("{"):
        return payload

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return payload

    code = data.get("code")
    if isinstance(code, str) and code.strip():
        return code
    return payload


def decode_mermaid_pako(payload: str) -> str:
    """Decode a Mermaid Live payload compressed with pako."""
    token = payload.strip()
    if not token:
        raise InvalidNodeError("Mermaid payload is empty")

    padding = (-len(token)) % 4
    if padding:
        token += "=" * padding

    try:
        compressed = base64.urlsafe_b64decode(token)
    except (binascii.Error, ValueError) as exc:
        raise InvalidNodeError("Mermaid payload is not valid base64") from exc

    last_error: Exception | None = None
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            data = zlib.decompress(compressed, wbits=wbits)
            try:
                extracted = data.decode("utf-8")
                return _extract_mermaid_code(extracted)
            except UnicodeDecodeError as exc:  # pragma: no cover - defensive
                raise InvalidNodeError("Mermaid payload is not UTF-8 text") from exc
        except zlib.error as exc:
            last_error = exc

    raise InvalidNodeError("Unable to decompress Mermaid payload") from last_error


def extract_mermaid_live_diagram(src: str) -> str | None:
    """Return Mermaid source encoded in a mermaid.live URL."""
    try:
        parsed = urlparse(src)
    except ValueError:
        return None

    if not parsed.netloc or not parsed.scheme:
        return None
    if not parsed.netloc.endswith("mermaid.live"):
        return None

    fragment = (parsed.fragment or "").strip()
    if not fragment:
        return None

    marker = fragment.find("pako:")
    if marker == -1:
        return None

    payload = fragment[marker + len("pako:") :]
    for delimiter in (";", "&"):
        idx = payload.find(delimiter)
        if idx != -1:
            payload = payload[:idx]

    if not payload:
        raise InvalidNodeError("Mermaid URL is missing diagram payload")

    return decode_mermaid_pako(payload)
