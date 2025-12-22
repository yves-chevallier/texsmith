"""Document abstractions used by the conversion pipeline.

Architecture
: `Document` models inputs alongside slot overrides and rendering toggles.
  Instances are intentionally lightweight so they can be duplicated when
  entering template sessions without costly reparsing.
: `Document` stores heading offsets, numbering, and slot overrides alongside
  the canonicalised HTML so the full conversion state lives in one place.

Implementation Rationale
: Conversions often need multiple passes over the same document, such as preview
  and templated export. By storing canonicalised HTML and front-matter snapshots
  we avoid repeated Markdown or HTML parsing.
: A dedicated abstraction makes it easy to inspect or mutate front matter in
  higher layers while keeping a single document shape throughout the conversion engine.

Usage Example
:
    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> from texsmith.core.documents import Document
    >>> with TemporaryDirectory() as tmpdir:
    ...     source = Path(tmpdir) / "chapter.md"
    ...     _ = source.write_text("# Chapter\\nBody")
    ...     doc = Document.from_markdown(source, base_level="section")
    ...     prepared = doc.prepare_for_conversion()
    ...     prepared.source_path.stem
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
from .conversion.debug import ConversionError, debug_enabled
from .conversion.inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    extract_content,
    extract_front_matter_slots,
)
from .conversion_contexts import AssetMapping, SegmentContext
from .diagnostics import DiagnosticEmitter, NullEmitter
from .metadata import PressMetadataError, normalise_press_metadata
from .templates.runtime import coerce_base_level


__all__ = [
    "Document",
    "TitleStrategy",
    "front_matter_has_title",
]

_SLOT_WILDCARDS: set[str] = {
    DOCUMENT_SELECTOR_SENTINEL,
    DOCUMENT_SELECTOR_SENTINEL.lower(),
    "*",
}


def _split_slot_mapping(mapping: Mapping[str, str]) -> tuple[dict[str, str], set[str]]:
    selectors: dict[str, str] = {}
    includes: set[str] = set()
    for slot, selector in mapping.items():
        slot_name = slot.strip()
        if not slot_name:
            continue
        token = selector.strip() if isinstance(selector, str) else ""
        if token.lower() in _SLOT_WILDCARDS:
            includes.add(slot_name)
        elif token:
            selectors[slot_name] = token
    return selectors, includes


def _slot_request_mapping(selectors: Mapping[str, str], includes: Iterable[str]) -> dict[str, str]:
    mapping = dict(selectors)
    for slot in includes:
        mapping.setdefault(slot, DOCUMENT_SELECTOR_SENTINEL)
    return mapping


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
class Document:
    """Renderable document used by the high-level API."""

    source_path: Path
    kind: InputKind
    _html: str
    _front_matter: Mapping[str, Any]
    base_level: int = 0
    title_strategy: TitleStrategy = TitleStrategy.KEEP
    numbered: bool = True
    suppress_title_metadata: bool = False
    slot_selectors: dict[str, str] = field(default_factory=dict)
    slot_includes: set[str] = field(default_factory=set)
    extracted_title: str | None = None
    slot_requests: dict[str, str] = field(default_factory=dict)
    slot_inclusions: set[str] = field(default_factory=set)
    language: str | None = None
    bibliography: dict[str, Any] = field(default_factory=dict)
    assets: list[AssetMapping] = field(default_factory=list)
    segments: dict[str, list[SegmentContext]] = field(default_factory=dict)
    _prepared_drop_title: bool | None = field(default=None, init=False, repr=False)

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
        document = cls(
            source_path=path,
            kind=InputKind.MARKDOWN,
            _html=rendered.html,
            _front_matter=rendered.front_matter,
            base_level=resolved_base_level,
            title_strategy=strategy,
            numbered=numbered_flag,
            suppress_title_metadata=suppress_title,
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
        document = cls(
            source_path=path,
            kind=InputKind.HTML,
            _html=html,
            _front_matter={},
            base_level=resolved_base_level,
            title_strategy=strategy,
            numbered=numbered,
            suppress_title_metadata=suppress_title,
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
            base_level=self.base_level,
            title_strategy=self.title_strategy,
            numbered=self.numbered,
            suppress_title_metadata=self.suppress_title_metadata,
            slot_selectors=copy.deepcopy(self.slot_selectors),
            slot_includes=set(self.slot_includes),
            extracted_title=None,
            slot_requests={},
            slot_inclusions=set(),
            language=None,
            bibliography={},
            assets=[],
            segments={},
        )

    @property
    def html(self) -> str:
        """Return the intermediate HTML content."""
        return self._html

    def set_html(self, html: str) -> None:
        """Replace the stored HTML payload."""
        self._html = html

    @property
    def front_matter(self) -> Mapping[str, Any]:
        """Return a deep copy of the front-matter mapping to keep stored state immutable."""
        return copy.deepcopy(self._front_matter)

    def set_front_matter(self, values: Mapping[str, Any]) -> None:
        """Replace the stored front matter with a deep copy to guard against caller mutation."""
        self._front_matter = copy.deepcopy(values)
        self._invalidate_prepared()

    @property
    def drop_title(self) -> bool:
        """Indicate whether the document title should be dropped."""
        if self._prepared_drop_title is not None:
            return self._prepared_drop_title
        if self.title_strategy is TitleStrategy.DROP:
            return True
        if self.title_strategy is TitleStrategy.PROMOTE_METADATA:
            title, should_drop = self._extract_promoted_title()
            if self.suppress_title_metadata:
                return False
            return bool(title and should_drop)
        return False

    @drop_title.setter
    def drop_title(self, value: bool) -> None:
        """Set whether the document title should be dropped."""
        if value:
            if self.title_strategy is TitleStrategy.PROMOTE_METADATA:
                return
            self.title_strategy = TitleStrategy.DROP
        else:
            if self.title_strategy is TitleStrategy.DROP:
                self.title_strategy = TitleStrategy.KEEP
        self._invalidate_prepared()

    @property
    def title_from_heading(self) -> bool:
        """Indicate whether the title should be extracted from the first heading."""
        if self._prepared_drop_title is not None:
            return bool(self.extracted_title)
        return self.title_strategy is TitleStrategy.PROMOTE_METADATA

    @title_from_heading.setter
    def title_from_heading(self, value: bool) -> None:
        """Set whether the title should be extracted from the first heading."""
        if value:
            self.title_strategy = TitleStrategy.PROMOTE_METADATA
        elif self.title_strategy is TitleStrategy.PROMOTE_METADATA:
            self.title_strategy = TitleStrategy.KEEP
        self._invalidate_prepared()

    def assign_slot(
        self,
        slot: str,
        selector: str | None = None,
        *,
        include_document: bool | None = None,
    ) -> None:
        """Map the document or a selector subset into a template slot."""
        slot_name = slot.strip()
        if not slot_name:
            return

        token = selector.strip() if isinstance(selector, str) else None
        include_flag = include_document

        if token:
            if token.lower() in _SLOT_WILDCARDS:
                include_flag = True if include_document is not False else include_document
                token = None
            else:
                self.slot_selectors[slot_name] = token
        elif selector is None and include_flag is None:
            include_flag = True

        if include_flag is True:
            self.slot_includes.add(slot_name)
        elif include_flag is False:
            self.slot_includes.discard(slot_name)

        if selector is None and include_flag is False:
            self.slot_selectors.pop(slot_name, None)
        self._invalidate_prepared()

    def reset_slots(self, mapping: Mapping[str, str] | None = None) -> None:
        """Replace slot selectors/inclusions with the provided mapping."""
        self.slot_selectors = {}
        self.slot_includes = set()
        if mapping:
            selectors, includes = _split_slot_mapping(mapping)
            self.slot_selectors.update(selectors)
            self.slot_includes.update(includes)
        self._invalidate_prepared()

    def _initialise_slots_from_front_matter(self) -> None:
        if isinstance(self._front_matter, Mapping):
            payload = dict(self._front_matter)
            with contextlib.suppress(PressMetadataError):
                normalise_press_metadata(payload)
            base_mapping = extract_front_matter_slots(payload)
            if base_mapping:
                selectors, includes = _split_slot_mapping(base_mapping)
                self.slot_selectors.update(selectors)
                self.slot_includes.update(includes)
        self._invalidate_prepared()

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

    def _invalidate_prepared(self) -> None:
        self._prepared_drop_title = None
        self.extracted_title = None
        self.slot_requests = {}
        self.slot_inclusions = set()
        self.language = None
        self.bibliography = {}
        self.assets = []
        self.segments = {}

    def prepare_for_conversion(self) -> Document:
        """Normalise metadata and slot requests so the document is ready for conversion."""
        strategy = self.title_strategy
        suppress_title = self.suppress_title_metadata
        promote_to_metadata = strategy is TitleStrategy.PROMOTE_METADATA and not suppress_title
        extracted_title = None
        drop_title_flag = strategy is TitleStrategy.DROP

        if promote_to_metadata:
            extracted_title, drop_title_flag = self._extract_promoted_title()

        front_matter = copy.deepcopy(self._front_matter)
        if suppress_title and isinstance(front_matter, dict):
            front_matter.pop("title", None)
            front_matter.pop("press.title", None)
            press_section = front_matter.get("press")
            if isinstance(press_section, dict):
                press_section.pop("title", None)

        metadata = dict(front_matter or {})
        try:
            press_payload = normalise_press_metadata(metadata)
        except PressMetadataError as exc:
            raise ConversionError(str(exc)) from exc
        metadata.setdefault("_source_dir", str(self.source_path.parent))
        metadata.setdefault("_source_path", str(self.source_path))
        if press_payload:
            press_payload.setdefault("_source_dir", str(self.source_path.parent))
            press_payload.setdefault("_source_path", str(self.source_path))

        base_mapping = extract_front_matter_slots(metadata)
        base_selectors, base_includes = _split_slot_mapping(base_mapping)
        combined_selectors = dict(base_selectors)
        combined_selectors.update(self.slot_selectors)
        combined_includes = set(base_includes)
        combined_includes.update(self.slot_includes)

        self._front_matter = metadata
        self.slot_selectors = dict(combined_selectors)
        self.slot_includes = set(combined_includes)
        self.slot_requests = _slot_request_mapping(combined_selectors, combined_includes)
        self.slot_inclusions = set(combined_includes)
        self.extracted_title = extracted_title
        self._prepared_drop_title = drop_title_flag
        self.language = None
        self.bibliography = {}
        self.assets = []
        self.segments = {}
        return self
