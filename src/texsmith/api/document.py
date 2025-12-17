"""Document abstractions consumed by the TeXSmith public API.

Architecture
: `Document` models inputs alongside slot overrides and rendering toggles.
  Instances are intentionally lightweight so they can be duplicated when
  entering template sessions without costly reparsing.
: `DocumentRenderOptions` captures heading offsets, numbering, and other knobs
  that influence the LaTeX output. Keeping these options separate from the core
  document data allows caller-specific tweaks while preserving the original
  source.

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
    ...     doc = Document.from_markdown(source, base_level="section")
    ...     context = doc.to_context()
    ...     context.name
    'chapter'
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import contextlib
import copy
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, ClassVar

from ..adapters.markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    MarkdownConversionError,
    render_markdown,
)
from ..core.conversion.debug import ConversionError, debug_enabled
from ..core.conversion.inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    build_document_context,
    extract_content,
    extract_front_matter_slots,
)
from ..core.conversion_contexts import DocumentContext
from ..core.diagnostics import DiagnosticEmitter, NullEmitter
from ..core.metadata import PressMetadataError, normalise_press_metadata
from ..core.templates.runtime import coerce_base_level


__all__ = [
    "Document",
    "DocumentRenderOptions",
    "DocumentSlots",
    "TitleStrategy",
    "front_matter_has_title",
]


class TitleStrategy(str, Enum):
    """Strategy describing how the first document heading should be handled."""

    KEEP = "keep"
    DROP = "drop"
    PROMOTE_METADATA = "promote_metadata"


def _resolve_title_strategy(
    *,
    explicit: TitleStrategy | None,
    promote_title: bool,
    strip_heading: bool,
    has_declared_title: bool,
) -> TitleStrategy:
    """Determine the effective title strategy from caller preferences."""
    if explicit is not None:
        return explicit
    if strip_heading:
        return TitleStrategy.DROP
    if promote_title and not has_declared_title:
        return TitleStrategy.PROMOTE_METADATA
    return TitleStrategy.KEEP


def front_matter_has_title(metadata: Mapping[str, Any] | None) -> bool:
    """Return ``True`` when the mapping declares a title."""
    if not isinstance(metadata, Mapping):
        return False

    payload = dict(metadata)
    with contextlib.suppress(PressMetadataError):
        normalise_press_metadata(payload)

    title = payload.get("title")
    return bool(isinstance(title, str) and title.strip())


def _coerce_bool(value: Any) -> bool | None:
    """Coerce loose truthy/falsey values from front matter."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {"true", "yes", "on", "1"}:
            return True
        if candidate in {"false", "no", "off", "0"}:
            return False
    return None


def _front_matter_numbered(metadata: Mapping[str, Any] | None) -> bool | None:
    """Extract a numbered flag from normalised front matter."""
    if not isinstance(metadata, Mapping):
        return None

    payload = dict(metadata)
    with contextlib.suppress(PressMetadataError):
        normalise_press_metadata(payload)
    return _coerce_bool(payload.get("numbered"))


@dataclass(slots=True)
class DocumentRenderOptions:
    """Rendering options applied when preparing a document context."""

    base_level: int = 0
    title_strategy: TitleStrategy = TitleStrategy.KEEP
    numbered: bool = True
    suppress_title_metadata: bool = False

    def copy(self) -> DocumentRenderOptions:
        """Return a deep copy of the options so mutations never leak across documents."""
        return DocumentRenderOptions(
            base_level=self.base_level,
            title_strategy=self.title_strategy,
            numbered=self.numbered,
            suppress_title_metadata=self.suppress_title_metadata,
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
        """Return a detached clone so callers can mutate slots without side effects."""
        return DocumentSlots(self._selectors, self._inclusions)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str] | None) -> DocumentSlots:
        """Build slots from stored metadata, normalising empty mappings to defaults."""
        slots = cls()
        if not mapping:
            return slots
        for slot, selector in mapping.items():
            slots.add(slot, selector=selector)
        return slots

    def merge(self, other: DocumentSlots) -> DocumentSlots:
        """Combine selectors and inclusions to preserve caller overrides."""
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
        """Register a slot directive, preserving explicit inclusion intent."""
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
        """Return slot names flagged for whole-document inclusion."""
        return set(self._inclusions)

    def selectors(self) -> dict[str, str]:
        """Return selectors mapped to slots, leaving the original untouched."""
        return dict(self._selectors)

    def to_request_mapping(self) -> dict[str, str]:
        """Render selectors into the request mapping expected by the engine."""
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
        promote_title: bool = False,
        strip_heading: bool = False,
        suppress_title: bool = False,
        base_level: int | str = 0,
        title_strategy: TitleStrategy | None = None,
        numbered: bool = True,
        emitter: DiagnosticEmitter | None = None,
    ) -> Document:
        """Create a document from a Markdown file while caching HTML for reuse."""
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

        try:
            resolved_base_level = coerce_base_level(base_level, allow_none=False)
        except Exception as exc:  # pragma: no cover - defensive
            message = f"Invalid base level '{base_level}': {exc}"
            active_emitter.error(message, exc if isinstance(exc, Exception) else None)
            raise ConversionError(message) from (
                exc if isinstance(exc, Exception) else ConversionError(message)
            )

        declared_title = front_matter_has_title(rendered.front_matter)
        strategy = _resolve_title_strategy(
            explicit=title_strategy,
            promote_title=promote_title,
            strip_heading=strip_heading,
            has_declared_title=declared_title,
        )
        front_numbered = _front_matter_numbered(rendered.front_matter)
        numbered_flag = numbered if front_numbered is None else front_numbered
        options = DocumentRenderOptions(
            base_level=resolved_base_level,
            title_strategy=strategy,
            numbered=numbered_flag,
            suppress_title_metadata=suppress_title,
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
        promote_title: bool = False,
        strip_heading: bool = False,
        suppress_title: bool = False,
        base_level: int | str = 0,
        title_strategy: TitleStrategy | None = None,
        numbered: bool = True,
        full_document: bool = False,
        emitter: DiagnosticEmitter | None = None,
    ) -> Document:
        """Create a document from an HTML file, extracting only the renderable region."""
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
                if debug_enabled(active_emitter):
                    message = (
                        f"CSS selector '{selector}' was not found in '{path.name}'. "
                        "Falling back to the full document."
                    )
                    active_emitter.warning(message, exc)

        try:
            resolved_base_level = coerce_base_level(base_level, allow_none=False)
        except Exception as exc:  # pragma: no cover - defensive
            message = f"Invalid base level '{base_level}': {exc}"
            active_emitter.error(message, exc if isinstance(exc, Exception) else None)
            raise ConversionError(message) from (
                exc if isinstance(exc, Exception) else ConversionError(message)
            )

        strategy = _resolve_title_strategy(
            explicit=title_strategy,
            promote_title=promote_title,
            strip_heading=strip_heading,
            has_declared_title=False,
        )
        options = DocumentRenderOptions(
            base_level=resolved_base_level,
            title_strategy=strategy,
            numbered=numbered,
            suppress_title_metadata=suppress_title,
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
        """Return a deep copy of the document to isolate later slot or metadata changes."""
        return Document(
            source_path=self.source_path,
            kind=self.kind,
            _html=self._html,
            _front_matter=copy.deepcopy(self._front_matter),
            options=self.options.copy(),
            slots=self.slots.copy(),
        )

    @property
    def html(self) -> str:
        """Return the intermediate HTML content."""
        return self._html

    @property
    def front_matter(self) -> Mapping[str, Any]:
        """Return a deep copy of the front-matter mapping to keep stored state immutable."""
        return copy.deepcopy(self._front_matter)

    def set_front_matter(self, values: Mapping[str, Any]) -> None:
        """Replace the stored front matter with a deep copy to guard against caller mutation."""
        self._front_matter = copy.deepcopy(values)

    @property
    def drop_title(self) -> bool:
        """Indicate whether the document title should be dropped."""
        if self.options.title_strategy is TitleStrategy.DROP:
            return True
        if self.options.title_strategy is TitleStrategy.PROMOTE_METADATA:
            title, should_drop = self._extract_promoted_title()
            if self.options.suppress_title_metadata:
                return False
            return bool(title and should_drop)
        return False

    @drop_title.setter
    def drop_title(self, value: bool) -> None:
        """Set whether the document title should be dropped."""
        if value:
            if self.options.title_strategy is TitleStrategy.PROMOTE_METADATA:
                return
            self.options.title_strategy = TitleStrategy.DROP
        else:
            if self.options.title_strategy is TitleStrategy.DROP:
                self.options.title_strategy = TitleStrategy.KEEP

    @property
    def title_from_heading(self) -> bool:
        """Indicate whether the title should be extracted from the first heading."""
        return self.options.title_strategy is TitleStrategy.PROMOTE_METADATA

    @title_from_heading.setter
    def title_from_heading(self, value: bool) -> None:
        """Set whether the title should be extracted from the first heading."""
        if value:
            self.options.title_strategy = TitleStrategy.PROMOTE_METADATA
        elif self.options.title_strategy is TitleStrategy.PROMOTE_METADATA:
            self.options.title_strategy = TitleStrategy.KEEP

    @property
    def numbered(self) -> bool:
        """Indicate whether the document is numbered."""
        return self.options.numbered

    @numbered.setter
    def numbered(self, value: bool) -> None:
        """Set whether the document is numbered."""
        self.options.numbered = bool(value)

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
            payload = dict(self._front_matter)
            with contextlib.suppress(PressMetadataError):
                normalise_press_metadata(payload)
            base_mapping = extract_front_matter_slots(payload)
            if base_mapping:
                self.slots.merge(DocumentSlots.from_mapping(base_mapping))

    _HEADING_TAGS: ClassVar[set[str]] = {"h1", "h2", "h3", "h4", "h5", "h6"}

    class _HeadingLevelScanner(HTMLParser):
        __slots__ = ("minimum_level",)

        def __init__(self) -> None:
            super().__init__()
            self.minimum_level: int | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if not tag:
                return
            name = tag.lower()
            if not name.startswith("h") or len(name) < 2 or not name[1].isdigit():
                return
            try:
                level = int(name[1])
            except ValueError:
                return
            if not 1 <= level <= 6:
                return
            if self.minimum_level is None or level < self.minimum_level:
                self.minimum_level = level

    @classmethod
    def _resolve_heading_alignment(cls, html: str, strategy: TitleStrategy) -> int:
        if strategy is not TitleStrategy.KEEP:
            return 0

        scanner = cls._HeadingLevelScanner()
        try:
            scanner.feed(html)
        finally:
            scanner.close()

        minimum = scanner.minimum_level
        if minimum is None or minimum <= 1:
            return 0
        return minimum - 1

    class _HeadingInspector(HTMLParser):
        __slots__ = ("_depth", "_resolved", "first_level", "level_counts", "parts")

        def __init__(self) -> None:
            super().__init__()
            self._depth = 0
            self._resolved = False
            self.first_level: int | None = None
            self.level_counts: dict[int, int] = {}
            self.parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            name = tag.lower()
            if not name.startswith("h") or len(name) < 2 or not name[1].isdigit():
                if self._depth:
                    self._depth += 1
                return

            try:
                level = int(name[1])
            except ValueError:
                if self._depth:
                    self._depth += 1
                return

            if not 1 <= level <= 6:
                if self._depth:
                    self._depth += 1
                return

            self.level_counts[level] = self.level_counts.get(level, 0) + 1
            if self._resolved:
                return

            if self.first_level is None:
                self.first_level = level
                self._depth = 1
                return

            if self._depth:
                self._depth += 1

        def handle_endtag(self, tag: str) -> None:
            if not self._depth:
                return
            self._depth -= 1
            if self._depth == 0:
                self._resolved = True

        def handle_data(self, data: str) -> None:
            if self._depth and not self._resolved:
                self.parts.append(data)

    def _extract_promoted_title(self) -> tuple[str | None, bool]:
        """Return the promoted title and whether the heading should be dropped."""
        inspector = self._HeadingInspector()
        try:
            inspector.feed(self._html)
        finally:
            inspector.close()

        if inspector.first_level is None:
            return None, False

        level_count = inspector.level_counts.get(inspector.first_level, 0)
        if level_count != 1:
            return None, False

        text = "".join(inspector.parts).strip()
        return (text or None, bool(text))

    def _first_heading_level(self) -> int | None:
        """Return the level of the first heading in the document, if any."""
        inspector = self._HeadingInspector()
        try:
            inspector.feed(self._html)
        finally:
            inspector.close()
        return inspector.first_level

    def first_heading_level(self) -> int | None:
        """Public accessor for the first heading level in the document."""
        return self._first_heading_level()

    def to_context(self) -> DocumentContext:
        """Build a fresh DocumentContext for conversion, aligning slots with engine expectations."""
        strategy = self.options.title_strategy
        suppress_title = self.options.suppress_title_metadata
        promote_to_metadata = strategy is TitleStrategy.PROMOTE_METADATA and not suppress_title
        extracted_title = None
        drop_title_flag = strategy is TitleStrategy.DROP

        if promote_to_metadata:
            extracted_title, drop_title_flag = self._extract_promoted_title()

        base_level = self.options.base_level
        front_matter = copy.deepcopy(self._front_matter)
        if suppress_title and isinstance(front_matter, dict):
            front_matter.pop("title", None)
            front_matter.pop("press.title", None)
            press_section = front_matter.get("press")
            if isinstance(press_section, dict):
                press_section.pop("title", None)

        context = build_document_context(
            name=self.source_path.stem,
            source_path=self.source_path,
            html=self._html,
            front_matter=front_matter,
            base_level=base_level,
            drop_title=drop_title_flag,
            numbered=self.options.numbered,
            title_from_heading=bool(extracted_title),
            extracted_title=extracted_title,
        )
        base_slots = DocumentSlots.from_mapping(context.slot_requests)
        combined_slots = base_slots.copy().merge(self.slots)
        self.slots = combined_slots.copy()
        context.slot_requests = combined_slots.to_request_mapping()
        context.slot_inclusions = combined_slots.includes()
        return context
