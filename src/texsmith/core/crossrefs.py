"""Cross-document references: publishing the reference inventory of a build.

A counter number only exists inside the conversion that allocated it, so a
second document citing ``FW-10`` has no way to know what ``FW-10`` is — and no
way to notice when a renumbering turns it into ``FW-12``. This module closes
that loop the way DocBook's *target database* and Sphinx's ``objects.inv`` do:
every conversion publishes a small JSON **inventory** next to its output, and a
citing document declares the inventories it depends on.

The inventory is written in two passes, because the two halves of a reference
become known at different times: TeXSmith knows the keys and their formatted
labels while converting, and the page numbers only exist once LaTeX has run —
they are harvested from the ``.aux`` afterwards, which is the same source the
``xr`` package reads.

A reference is rendered from the target document's own identity: when it
declares a ``document-id`` (a free label such as ``RHE-423``) the citation
concatenates it with the anchor's label (``RHE-423-FW-10``), otherwise it falls
back to naming the document by its title.

Reading an inventory is tmark's: its registry loads the sources a document
declares under ``press.sources.crossrefs`` through the ``Loader`` and resolves
``@alias:key`` at resolve time (decision D4). What stays here is the writing
half — the payload, the anchors of a finished resolution, the page numbers
harvested from the ``.aux`` and the relocation that keeps ``document.source``
resolvable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any


#: Bumped when the on-disk shape changes in a way older readers cannot handle.
SCHEMA_VERSION = 1

#: Suffix of the published inventory, sibling of the rendered document.
INVENTORY_SUFFIX = ".refs.json"


@dataclass(frozen=True, slots=True)
class Anchor:
    """One citable item published by a document."""

    key: str
    label: str
    counter: str = ""
    page: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentIdentity:
    """Who published an inventory, and from what."""

    id: str = ""
    title: str = ""
    output: str = ""
    source: str = ""
    source_sha256: str = ""


# Writing


def build_payload(
    *,
    anchors: Mapping[str, Anchor],
    identity: DocumentIdentity,
) -> dict[str, Any]:
    """Return the JSON payload of an inventory, with anchors in key order."""
    return {
        "schema": SCHEMA_VERSION,
        "document": {
            "id": identity.id,
            "title": identity.title,
            "output": identity.output,
            "source": identity.source,
            "source_sha256": identity.source_sha256,
        },
        "anchors": {
            key: {
                **({"counter": anchor.counter} if anchor.counter else {}),
                "label": anchor.label,
                **({"page": anchor.page} if anchor.page is not None else {}),
            }
            for key, anchor in sorted(anchors.items())
        },
    }


def write_inventory(path: Path | str, payload: Mapping[str, Any]) -> Path:
    """Write an inventory as pretty JSON so its diffs stay readable."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


#: The ``labels`` host of a ``{counter}(prefix:key)`` item in a ``tmark.resolve``
#: result. Headers, floats and theorem kinds are numbered by the backend and are
#: not citable across documents; a declared counter series is.
_COUNTER_HOST = "counter_item"


def anchors_from_resolved(resolved: Mapping[str, Any] | None) -> dict[str, Anchor]:
    """The citable anchors of a ``tmark.resolve`` result, keyed by ``prefix:key``.

    Every label tmark allocated for a declared counter series becomes an anchor
    carrying its formatted number, which is exactly what a citing document
    prints for ``@alias:prefix:key``.
    """
    if not isinstance(resolved, Mapping):
        return {}
    anchors: dict[str, Anchor] = {}
    for label in resolved.get("labels") or ():
        if not isinstance(label, Mapping) or label.get("host") != _COUNTER_HOST:
            continue
        identifier = str(label.get("id") or "").strip()
        if not identifier:
            continue
        anchors[identifier] = Anchor(
            key=identifier,
            label=str(label.get("formatted") or ""),
            counter=str(label.get("prefix") or "") or None,
        )
    return anchors


#: The document's own reference number, in order of preference. ``id`` is the
#: spelling authors reach for; ``document-id`` stays accepted since it is what
#: the first documentation shipped.
_IDENTIFIER_KEYS = ("id", "document-id")


def document_identifier(metadata: Mapping[str, Any] | None) -> str:
    """Return the free label a document publishes itself under, if any."""
    if not isinstance(metadata, Mapping):
        return ""
    for key in _IDENTIFIER_KEYS:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def publish_inventory(
    *,
    output_dir: Path | str,
    stem: str,
    metadata: Mapping[str, Any] | None,
    source_path: Path | str | None,
    anchors: Mapping[str, Anchor],
    output_name: str = "",
) -> Path | None:
    """Write the inventory of a finished conversion, or ``None`` if it has nothing to publish."""
    if not anchors:
        return None

    payload_metadata: Mapping[str, Any] = metadata or {}
    directory = Path(output_dir)
    source = ""
    if source_path is not None:
        try:
            source = os.path.relpath(Path(source_path).resolve(), directory.resolve())
        except (OSError, ValueError):  # pragma: no cover - different drives
            source = Path(source_path).name

    identity = DocumentIdentity(
        id=document_identifier(payload_metadata),
        title=str(payload_metadata.get("title") or "").strip(),
        output=output_name or f"{stem}.pdf",
        source=source,
        source_sha256=source_digest(source_path) if source_path is not None else "",
    )
    return write_inventory(
        directory / f"{stem}{INVENTORY_SUFFIX}",
        build_payload(anchors=dict(anchors), identity=identity),
    )


def attach_pages(inventory_path: Path | str, aux_path: Path | str) -> int:
    """Fold the page numbers of a finished LaTeX run into an existing inventory.

    Returns how many anchors were updated.
    """
    target = Path(inventory_path)
    pages = harvest_aux(aux_path)
    if not pages or not target.exists():
        return 0
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return 0

    anchors = payload.get("anchors")
    if not isinstance(anchors, dict):
        return 0
    updated = 0
    for key, anchor in anchors.items():
        page = pages.get(key)
        if page is None or not isinstance(anchor, dict) or anchor.get("page") == page:
            continue
        anchor["page"] = page
        updated += 1
    if updated:
        write_inventory(target, payload)
    return updated


def relocate_inventory(inventory_path: Path | str, destination_dir: Path | str) -> Path | None:
    """Deliver an inventory next to the artifact, keeping ``document.source`` resolvable.

    ``source`` is stored relative to the inventory's own location and is what
    the staleness check reads: copying the file verbatim would leave a path that
    no longer resolves, and the check would go quietly inoperative — exactly the
    failure mode this feature exists to remove. So the path is recomputed.
    """
    source_inventory = Path(inventory_path)
    destination = Path(destination_dir)
    if not source_inventory.exists():
        return None
    target = destination / source_inventory.name
    if target.resolve() == source_inventory.resolve():
        return target

    try:
        payload = json.loads(source_inventory.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return None

    document = payload.get("document")
    if isinstance(document, dict) and document.get("source"):
        original = (source_inventory.parent / str(document["source"])).resolve()
        try:
            document["source"] = os.path.relpath(original, destination.resolve())
        except (OSError, ValueError):  # pragma: no cover - different drives
            document["source"] = original.name
    return write_inventory(target, payload)


def source_digest(path: Path | str) -> str:
    """Return the SHA-256 of a source file, or an empty string when unreadable."""
    try:
        return sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


# Page harvesting


def harvest_aux(path: Path | str) -> dict[str, int]:
    """Return ``{label: page}`` for every ``\\newlabel`` of a LaTeX ``.aux``.

    This is the same source the ``xr`` package reads. The fields are parsed
    with a real brace counter because the first one routinely carries nested
    TeX markup (``{\\relax 2.1}``) that a regular expression would trip on.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    pages: dict[str, int] = {}
    for match in re.finditer(r"\\newlabel\{", text):
        cursor = match.end()
        key, cursor = _read_braced(text, cursor - 1)
        if key is None:
            continue
        body, _ = _read_braced(text, cursor)
        if body is None:
            continue
        fields = _split_braced(body)
        if len(fields) < 2:
            continue
        page = fields[1].strip()
        if page.isdigit():
            pages[key] = int(page)
    return pages


def _read_braced(text: str, start: int) -> tuple[str | None, int]:
    """Read the brace-delimited group starting at ``text[start] == '{'``."""
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    return None, len(text)


def _split_braced(text: str) -> list[str]:
    """Split a ``{a}{b}{c}`` run into its top-level groups."""
    fields: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "{":
            cursor += 1
            continue
        field_text, cursor = _read_braced(text, cursor)
        if field_text is None:
            break
        fields.append(field_text)
    return fields


__all__ = [
    "INVENTORY_SUFFIX",
    "SCHEMA_VERSION",
    "Anchor",
    "DocumentIdentity",
    "anchors_from_resolved",
    "attach_pages",
    "build_payload",
    "document_identifier",
    "harvest_aux",
    "publish_inventory",
    "relocate_inventory",
    "source_digest",
    "write_inventory",
]
