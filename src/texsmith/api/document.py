"""Document abstractions consumed by the TeXSmith public API.

Architecture
: `Document` models inputs alongside slot overrides and rendering toggles.
  Instances are intentionally lightweight so they can be duplicated when
  entering template sessions without costly reparsing.
: `DocumentRenderOptions` captures heading offsets, numbering, and other knobs
  that influence the LaTeX output. Keeping these options separate from the core
  document data allows caller-specific tweaks while preserving the original
  source.
: `HeadingLevel` and `resolve_heading_level` provide a friendly bridge between
  human labels (for example `"section"`) and the numeric levels required by the
  LaTeX engine. This mapping is shared across the CLI and programmatic surfaces
  to guarantee consistent behaviour.

Implementation Rationale
: Conversions often need multiple passes over the same document, such as preview
  and templated export. By storing canonicalised HTML and front-matter snapshots
  we avoid repeated Markdown or HTML parsing.
: A dedicated abstraction makes it easy to inspect or mutate front matter in
  higher layers without leaking the underlying `DocumentContext` type used
  deeper inside the conversion engine.

Usage Example
:
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> from texsmith.api.document import Document
    >>> with TemporaryDirectory() as tmpdir:
    ...     source = Path(tmpdir) / "chapter.md"
    ...     _ = source.write_text("# Chapter\\nBody")
    ...     doc = Document.from_markdown(source, heading="section")
    ...     context = doc.to_context()
    ...     context.name
    'chapter'
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from ..adapters.markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    MarkdownConversionError,
    render_markdown,
)
from ..core.conversion.debug import ConversionError
from ..core.conversion.inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    build_document_context,
    extract_content,
    extract_front_matter_slots,
)
from ..core.conversion_contexts import DocumentContext
from ..core.diagnostics import DiagnosticEmitter, NullEmitter
from ..core.templates import LATEX_HEADING_LEVELS


__all__ = [
    "Document",
    "DocumentRenderOptions",
    "DocumentSlots",
    "HeadingLevel",
    "resolve_heading_level",
]


class HeadingLevel(int):
    """Represents a LaTeX heading depth."""

    @classmethod
    def from_label(cls, value: str | int | HeadingLevel) -> HeadingLevel:
        """Create a HeadingLevel from a label or numeric depth."""
        if isinstance(value, HeadingLevel):
            return value
        if isinstance(value, int):
            return cls(value)
        key = value.strip().lower()
        if key not in LATEX_HEADING_LEVELS:
            allowed = ", ".join(sorted(LATEX_HEADING_LEVELS))
            raise ValueError(f"Unknown heading label '{value}'. Expected one of: {allowed}.")
        return cls(LATEX_HEADING_LEVELS[key])


def resolve_heading_level(value: str | int | HeadingLevel) -> int:
    """Resolve a heading descriptor into a numeric level."""
    return int(HeadingLevel.from_label(value))


@dataclass(slots=True)
class DocumentRenderOptions:
    """Rendering options applied when preparing a document context."""

    base_level: int = 0
    heading_level: int = 0
    drop_title: bool = False
    numbered: bool = True

    def copy(self) -> DocumentRenderOptions:
        """Return a deep copy of the options."""
        return DocumentRenderOptions(
            base_level=self.base_level,
            heading_level=self.heading_level,
            drop_title=self.drop_title,
            numbered=self.numbered,
        )


class DocumentSlots:
    """Container tracking slot selectors and inclusion directives."""

    __slots__ = ("_inclusions", "_selectors")

    _WILDCARDS: ClassVar[set[str]] = {
        DOCUMENT_SELECTOR_SENTINEL,
        DOCUMENT_SELECTOR_SENTINEL.lower(),
        "*",
    }

    def __init__(
        self,
        selectors: Mapping[str, str] | None = None,
        inclusions: Iterable[str] | None = None,
    ) -> None:
        self._selectors: dict[str, str] = dict(selectors or {})
        self._inclusions: set[str] = {slot.strip() for slot in inclusions or [] if slot}

    def copy(self) -> DocumentSlots:
        return DocumentSlots(self._selectors, self._inclusions)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str] | None) -> DocumentSlots:
        slots = cls()
        if not mapping:
            return slots
        for slot, selector in mapping.items():
            slots.add(slot, selector=selector)
        return slots

    def merge(self, other: DocumentSlots) -> DocumentSlots:
        if other is self:
            return self
        self._selectors.update(other._selectors)
        self._inclusions.update(other._inclusions)
        return self

    def add(
        self,
        slot: str,
        *,
        selector: str | None = None,
        include_document: bool | None = None,
    ) -> DocumentSlots:
        slot_name = slot.strip()
        if not slot_name:
            return self

        token = selector.strip() if isinstance(selector, str) else None
        include_flag = include_document

        if token:
            if token.lower() in self._WILDCARDS:
                include_flag = True if include_document is not False else include_document
                token = None
            else:
                self._selectors[slot_name] = token
        elif selector is None and include_flag is None:
            include_flag = True

        if include_flag is True:
            self._inclusions.add(slot_name)
        elif include_flag is False:
            self._inclusions.discard(slot_name)

        if selector is None and include_flag is False:
            self._selectors.pop(slot_name, None)

        return self

    def includes(self) -> set[str]:
        return set(self._inclusions)

    def selectors(self) -> dict[str, str]:
        return dict(self._selectors)

    def to_request_mapping(self) -> dict[str, str]:
        mapping = dict(self._selectors)
        for slot in self._inclusions:
            mapping.setdefault(slot, DOCUMENT_SELECTOR_SENTINEL)
        return mapping

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return bool(self._selectors or self._inclusions)


@dataclass(slots=True)
class Document:
    """Renderable document used by the high-level API."""

    source_path: Path
    kind: InputKind
    _html: str
    _front_matter: Mapping[str, Any]
    options: DocumentRenderOptions = field(default_factory=DocumentRenderOptions)
    slots: DocumentSlots = field(default_factory=DocumentSlots)

    @classmethod
    def from_markdown(
        cls,
        path: Path,
        *,
        extensions: Iterable[str] | None = None,
        heading: str | int | HeadingLevel = 0,
        base_level: int = 0,
        drop_title: bool = False,
        numbered: bool = True,
        emitter: DiagnosticEmitter | None = None,
    ) -> Document:
        """Create a document from a Markdown file."""
        active_emitter = emitter or NullEmitter()

        try:
            rendered = render_markdown(
                path.read_text(encoding="utf-8"),
                list(extensions or DEFAULT_MARKDOWN_EXTENSIONS),
                base_path=path.parent,
            )
        except (OSError, MarkdownConversionError) as exc:
            message = f"Failed to convert Markdown source '{path}': {exc}"
            active_emitter.error(message, exc if isinstance(exc, Exception) else None)
            raise ConversionError(message) from (
                exc if isinstance(exc, Exception) else ConversionError(message)
            )

        options = DocumentRenderOptions(
            base_level=base_level,
            heading_level=resolve_heading_level(heading),
            drop_title=drop_title,
            numbered=numbered,
        )
        document = cls(
            source_path=path,
            kind=InputKind.MARKDOWN,
            _html=rendered.html,
            _front_matter=rendered.front_matter,
            options=options,
            slots=DocumentSlots(),
        )
        document._initialise_slots_from_front_matter()
        return document

    @classmethod
    def from_html(
        cls,
        path: Path,
        *,
        selector: str = "article.md-content__inner",
        heading: str | int | HeadingLevel = 0,
        base_level: int = 0,
        drop_title: bool = False,
        numbered: bool = True,
        full_document: bool = False,
        emitter: DiagnosticEmitter | None = None,
    ) -> Document:
        """Create a document from an HTML file."""
        active_emitter = emitter or NullEmitter()

        try:
            payload = path.read_text(encoding="utf-8")
        except OSError as exc:
            message = f"Failed to read HTML document '{path}': {exc}"
            active_emitter.error(message, exc)
            raise ConversionError(message) from exc

        html = payload
        if not full_document:
            try:
                html = extract_content(payload, selector)
            except ValueError as exc:
                message = (
                    f"CSS selector '{selector}' was not found in '{path.name}'. "
                    "Falling back to the full document."
                )
                active_emitter.warning(message, exc)

        options = DocumentRenderOptions(
            base_level=base_level,
            heading_level=resolve_heading_level(heading),
            drop_title=drop_title,
            numbered=numbered,
        )
        document = cls(
            source_path=path,
            kind=InputKind.HTML,
            _html=html,
            _front_matter={},
            options=options,
            slots=DocumentSlots(),
        )
        document._initialise_slots_from_front_matter()
        return document

    def copy(self) -> Document:
        """Return a deep copy of the document."""
        return Document(
            source_path=self.source_path,
            kind=self.kind,
            _html=self._html,
            _front_matter=copy.deepcopy(self._front_matter),
            options=self.options.copy(),
            slots=self.slots.copy(),
        )

    @property
    def front_matter(self) -> Mapping[str, Any]:
        """Return a deep copy of the front-matter mapping."""
        return copy.deepcopy(self._front_matter)

    def set_front_matter(self, values: Mapping[str, Any]) -> None:
        """Replace the stored front matter with a deep copy of the mapping."""
        self._front_matter = copy.deepcopy(values)

    @property
    def drop_title(self) -> bool:
        """Indicate whether the document title should be dropped."""
        return self.options.drop_title

    @drop_title.setter
    def drop_title(self, value: bool) -> None:
        """Set whether the document title should be dropped."""
        self.options.drop_title = bool(value)

    @property
    def numbered(self) -> bool:
        """Indicate whether the document is numbered."""
        return self.options.numbered

    @numbered.setter
    def numbered(self, value: bool) -> None:
        """Set whether the document is numbered."""
        self.options.numbered = bool(value)

    def set_heading(self, heading: str | int | HeadingLevel) -> None:
        """Update the heading level using a label or numeric depth."""
        self.options.heading_level = resolve_heading_level(heading)

    def assign_slot(
        self,
        slot: str,
        selector: str | None = None,
        *,
        include_document: bool | None = None,
    ) -> None:
        """Map the document or a selector subset into a template slot."""
        self.slots.add(slot, selector=selector, include_document=include_document)

    def _initialise_slots_from_front_matter(self) -> None:
        if isinstance(self._front_matter, Mapping):
            base_mapping = extract_front_matter_slots(self._front_matter)
            if base_mapping:
                self.slots.merge(DocumentSlots.from_mapping(base_mapping))

    def to_context(self) -> DocumentContext:
        """Build a fresh DocumentContext for conversion."""
        context = build_document_context(
            name=self.source_path.stem,
            source_path=self.source_path,
            html=self._html,
            front_matter=copy.deepcopy(self._front_matter),
            base_level=self.options.base_level,
            heading_level=self.options.heading_level,
            drop_title=self.options.drop_title,
            numbered=self.options.numbered,
        )
        base_slots = DocumentSlots.from_mapping(context.slot_requests)
        combined_slots = base_slots.copy().merge(self.slots)
        self.slots = combined_slots.copy()
        context.slot_requests = combined_slots.to_request_mapping()
        context.slot_inclusions = combined_slots.includes()
        return context

    @property
    def slot_inclusions(self) -> set[str]:
        """Expose slot inclusions for compatibility with existing code paths."""
        return self.slots.includes()

    @property
    def slot_overrides(self) -> dict[str, str]:
        """Expose slot selectors for compatibility with existing code paths."""
        return self.slots.selectors()
