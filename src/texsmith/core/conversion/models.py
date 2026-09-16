"""SSOT model for conversion settings and requests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from texsmith.diagnostics import DiagnosticEmitter


@dataclass(slots=True)
class SlotAssignment:
    """Directive mapping a document onto a template slot."""

    slot: str
    selector: str | None
    include_document: bool


@dataclass(slots=True, frozen=True)
class ConversionRequest:
    """Immutable description of conversion inputs and engine settings.

    Frozen, so the docstring holds: a caller that needs a variation asks for
    one with :meth:`replace`, which deep-copies every field but the emitter.
    """

    documents: Sequence[Path] = field(default_factory=tuple)
    bibliography_files: Sequence[Path] = field(default_factory=list)
    front_matter: Mapping[str, Any] | None = None
    front_matter_paths: Sequence[Path] = field(default_factory=tuple)
    slot_assignments: Mapping[Path, Sequence[SlotAssignment]] = field(default_factory=dict)

    #: Directories an include falls back to when its path does not resolve
    #: against the including file (``--include-path``). Searched first, before
    #: the document's own ``press.include_paths``.
    include_paths: Sequence[Path] = field(default_factory=tuple)
    #: The same search path, supplied by the host rather than by the user (the
    #: MkDocs companion passes the site's ``pymdownx.snippets`` base path here).
    #: Searched last, after the document's ``press.include_paths``.
    default_include_paths: Sequence[Path] = field(default_factory=tuple)
    #: The directory a root-relative asset path (``/assets/logo.png``) resolves
    #: against: the site's ``docs_dir``, which is MkDocs'
    #: ``validation.absolute_links: relative_to_docs`` rule. ``None`` — a
    #: standalone conversion — leaves such a path a filesystem path.
    root_dir: Path | None = None

    base_level: int = 0
    strip_heading_all: bool = False
    strip_heading_first_document: bool = False
    promote_title: bool = True
    suppress_title: bool = False
    numbered: bool = True

    template: str | None = None
    render_dir: Path | None = None
    template_options: Mapping[str, Any] = field(default_factory=dict)
    embed_documents: bool = False
    enable_fragments: Sequence[str] = field(default_factory=tuple)
    disable_fragments: Sequence[str] = field(default_factory=tuple)

    copy_assets: bool = True
    convert_assets: bool = False
    hash_assets: bool = False
    manifest: bool = False
    persist_debug_ir: bool = False
    language: str | None = None
    http_user_agent: str | None = None
    legacy_latex_accents: bool = False
    diagrams_backend: str | None = None

    emitter: DiagnosticEmitter | None = None

    def replace(self, **changes: Any) -> ConversionRequest:
        """A deep copy of this request with ``changes`` applied.

        The emitter is shared, not copied: it collects the run's diagnostics
        and a copy would collect nothing.
        """
        payload: dict[str, Any] = {}
        for definition in fields(self):
            if definition.name in changes:
                payload[definition.name] = changes[definition.name]
                continue
            value = getattr(self, definition.name)
            payload[definition.name] = (
                value if definition.name == "emitter" else copy.deepcopy(value)
            )
        unknown = set(changes) - {definition.name for definition in fields(self)}
        if unknown:
            raise TypeError(f"ConversionRequest has no field(s): {', '.join(sorted(unknown))}")
        return ConversionRequest(**payload)
