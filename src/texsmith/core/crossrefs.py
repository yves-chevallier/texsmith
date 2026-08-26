"""Cross-document references: publishing and consuming reference inventories.

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
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any

from texsmith.core.diagnostics import warn_author as _warn


#: Bumped when the on-disk shape changes in a way older readers cannot handle.
SCHEMA_VERSION = 1

#: Suffix of the published inventory, sibling of the rendered document.
INVENTORY_SUFFIX = ".refs.json"


class CrossRefValidationError(ValueError):
    """Raised when the front-matter ``crossrefs`` section is invalid."""


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


@dataclass(frozen=True, slots=True)
class Inventory:
    """A parsed ``*.refs.json`` document."""

    document: DocumentIdentity
    anchors: dict[str, Anchor] = field(default_factory=dict)
    path: Path | None = None

    def anchor(self, key: str) -> Anchor | None:
        """Return the anchor published under ``key``, if any."""
        return self.anchors.get(key)


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


def parse_front_matter_crossrefs(
    metadata: Mapping[str, Any] | None,
    *,
    base_path: Path | str | None = None,
) -> dict[str, Path]:
    """Validate the ``crossrefs:`` front-matter section into ``alias -> path``.

    Paths are resolved against ``base_path`` — the directory of the citing
    document — so a relative ``../build/x.refs.json`` means what it reads like.
    """
    if not isinstance(metadata, Mapping):
        return {}

    raw = metadata.get("crossrefs")
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise CrossRefValidationError(
            "Front-matter 'crossrefs' must be a mapping of alias -> inventory path."
        )

    root = Path(base_path) if base_path is not None else Path()
    sources: dict[str, Path] = {}
    for raw_alias, value in raw.items():
        alias = str(raw_alias).strip()
        if not alias:
            raise CrossRefValidationError("A cross-reference alias may not be empty.")

        if isinstance(value, str):
            # Shorthand: ``fwrev: ../build/firmware-review.refs.json``.
            inventory = value.strip()
        elif isinstance(value, Mapping):
            unknown = set(value) - {"inventory"}
            if unknown:
                raise CrossRefValidationError(
                    f"Cross-reference '{alias}' has unknown option(s): "
                    f"{', '.join(sorted(unknown))}."
                )
            inventory = str(value.get("inventory") or "").strip()
        else:
            raise CrossRefValidationError(
                f"Cross-reference '{alias}' must be a path or a mapping, "
                f"got {type(value).__name__}."
            )

        if not inventory:
            raise CrossRefValidationError(f"Cross-reference '{alias}' has no 'inventory' path.")
        sources[alias] = (root / inventory).resolve()

    return sources


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def load_inventory(path: Path | str, *, origin: Path | str | None = None) -> Inventory | None:
    """Read an inventory from disk, warning (not raising) when unusable.

    ``origin`` is the citing document, used to attribute the warnings.
    """
    candidate = Path(path)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _warn(
            f"Cross-reference inventory '{candidate}' is missing; "
            "build the document it describes first.",
            origin,
        )
        return None
    except (OSError, json.JSONDecodeError) as exc:
        _warn(f"Cross-reference inventory '{candidate}' could not be read: {exc}", origin)
        return None

    if not isinstance(payload, Mapping):
        _warn(f"Cross-reference inventory '{candidate}' is not a JSON object.", origin)
        return None
    schema = payload.get("schema")
    if schema != SCHEMA_VERSION:
        _warn(
            f"Cross-reference inventory '{candidate}' uses schema {schema}, "
            f"this TeXSmith reads {SCHEMA_VERSION}.",
            origin,
        )
        return None

    raw_document = payload.get("document")
    document = DocumentIdentity(
        id=str((raw_document or {}).get("id") or ""),
        title=str((raw_document or {}).get("title") or ""),
        output=str((raw_document or {}).get("output") or ""),
        source=str((raw_document or {}).get("source") or ""),
        source_sha256=str((raw_document or {}).get("source_sha256") or ""),
    )

    anchors: dict[str, Anchor] = {}
    for key, raw_anchor in (payload.get("anchors") or {}).items():
        if not isinstance(raw_anchor, Mapping):
            continue
        page = raw_anchor.get("page")
        anchors[str(key)] = Anchor(
            key=str(key),
            label=str(raw_anchor.get("label") or ""),
            counter=str(raw_anchor.get("counter") or ""),
            page=int(page) if isinstance(page, int) else None,
        )

    inventory = Inventory(document=document, anchors=anchors, path=candidate)
    _warn_if_stale(inventory, origin=origin)
    return inventory


def _warn_if_stale(inventory: Inventory, *, origin: Path | str | None = None) -> None:
    """Warn when the described source has changed since the inventory was written.

    A stale inventory silently reintroduces exactly the drift the feature
    exists to remove, so this is the one check worth paying for on every read.
    """
    identity = inventory.document
    if not identity.source or not identity.source_sha256 or inventory.path is None:
        return
    source = (inventory.path.parent / identity.source).resolve()
    try:
        digest = sha256(source.read_bytes()).hexdigest()
    except OSError:
        # Silence here would be the worst outcome: the inventory claims to know
        # what it describes, but nothing can check that claim any more.
        _warn(
            f"Cross-reference inventory '{inventory.path}' records a source "
            f"('{identity.source}') that does not resolve; it can no longer be "
            "checked for staleness.",
            origin,
        )
        return
    if digest != identity.source_sha256:
        _warn(
            f"Cross-reference inventory '{inventory.path}' is out of date: "
            f"'{source}' changed since it was written. Rebuild that document.",
            origin,
        )


# ---------------------------------------------------------------------------
# Rendering a citation
# ---------------------------------------------------------------------------


def render_reference(identity: DocumentIdentity, anchor: Anchor) -> str:
    """Return the text a ``@alias:key`` citation renders to.

    ``RHE-423-FW-10 p. 14`` when the target declares an ``id``; ``FW-10 (Revue
    firmware, p. 14)`` when only its title identifies it; and the bare label
    when it has neither — which is still better than dropping the reference.
    The page is omitted until the target has been built at least once.
    """
    if identity.id:
        suffix = f" p. {anchor.page}" if anchor.page is not None else ""
        return f"{identity.id}-{anchor.label}{suffix}"
    if identity.title:
        suffix = f", p. {anchor.page}" if anchor.page is not None else ""
        return f"{anchor.label} ({identity.title}{suffix})"
    suffix = f" p. {anchor.page}" if anchor.page is not None else ""
    return f"{anchor.label}{suffix}"


@dataclass(slots=True)
class CrossRefResolver:
    """Resolve ``alias:key`` citations against the declared inventories.

    Inventories are read on first use, so a document that declares a dependency
    it never cites pays nothing — and the "missing inventory" warning is raised
    once per alias rather than once per citation.
    """

    sources: dict[str, Path] = field(default_factory=dict)
    origin: Path | str | None = None
    _inventories: dict[str, Inventory | None] = field(default_factory=dict)
    _missing: set[str] = field(default_factory=set)

    def knows(self, alias: str) -> bool:
        """Whether ``alias`` was declared in the front matter."""
        return alias in self.sources

    def inventory(self, alias: str) -> Inventory | None:
        """Return (and cache) the inventory declared under ``alias``."""
        if alias not in self._inventories:
            path = self.sources.get(alias)
            self._inventories[alias] = (
                load_inventory(path, origin=self.origin) if path is not None else None
            )
        return self._inventories[alias]

    def resolve(self, alias: str, key: str) -> str | None:
        """Return the rendered citation, or ``None`` after warning about it."""
        if alias not in self.sources:
            return None
        inventory = self.inventory(alias)
        if inventory is None:
            return None
        anchor = inventory.anchor(key)
        if anchor is None:
            token = f"{alias}:{key}"
            if token not in self._missing:
                self._missing.add(token)
                _warn(
                    f"Cross-reference '@{token}' is not published by "
                    f"'{inventory.path}'; it may have been renamed or removed.",
                    self.origin,
                )
            return None
        return render_reference(inventory.document, anchor)

    @property
    def unresolved(self) -> tuple[str, ...]:
        """Citations that could not be resolved, for a strict-mode gate."""
        return tuple(sorted(self._missing))


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


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


def anchors_from_counters() -> dict[str, Anchor]:
    """Return the citable anchors allocated by the counter registry."""
    from texsmith.core.counters import get_registry

    registry = get_registry()
    anchors: dict[str, Anchor] = {}
    for prefix, keys in registry.snapshot().items():
        for key in keys:
            identifier = f"{prefix}:{key}"
            anchors[identifier] = Anchor(
                key=identifier,
                label=registry.render(prefix, key) or "",
                counter=prefix,
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
    output_name: str = "",
) -> Path | None:
    """Write the inventory of a finished conversion, or ``None`` if it has nothing to publish."""
    anchors = anchors_from_counters()
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
        build_payload(anchors=anchors, identity=identity),
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


# ---------------------------------------------------------------------------
# Page harvesting
# ---------------------------------------------------------------------------


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
    "CrossRefResolver",
    "CrossRefValidationError",
    "DocumentIdentity",
    "Inventory",
    "anchors_from_counters",
    "attach_pages",
    "build_payload",
    "document_identifier",
    "harvest_aux",
    "load_inventory",
    "parse_front_matter_crossrefs",
    "publish_inventory",
    "relocate_inventory",
    "render_reference",
    "source_digest",
    "write_inventory",
]
