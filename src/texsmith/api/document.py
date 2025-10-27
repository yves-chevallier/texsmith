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
from typing import Any

from ..domain.conversion.debug import ConversionCallbacks, ConversionError
from ..domain.conversion.inputs import InputKind, build_document_context, extract_content
from ..domain.conversion_contexts import DocumentContext
from ..markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    MarkdownConversionError,
    render_markdown,
)
from ..templates import LATEX_HEADING_LEVELS


__all__ = [
    "Document",
    "DocumentRenderOptions",
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


@dataclass(slots=True)
class Document:
    """Renderable document used by the high-level API."""

    source_path: Path
    kind: InputKind
    _html: str
    _front_matter: Mapping[str, Any]
    options: DocumentRenderOptions = field(default_factory=DocumentRenderOptions)
    slot_overrides: dict[str, str] = field(default_factory=dict)
    slot_inclusions: set[str] = field(default_factory=set)

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
        callbacks: ConversionCallbacks | None = None,
    ) -> Document:
        """Create a document from a Markdown file."""
        try:
            rendered = render_markdown(
                path.read_text(encoding="utf-8"),
                list(extensions or DEFAULT_MARKDOWN_EXTENSIONS),
            )
        except (OSError, MarkdownConversionError) as exc:
            message = f"Failed to convert Markdown source '{path}': {exc}"
            if callbacks and callbacks.emit_error:
                callbacks.emit_error(message, exc if isinstance(exc, Exception) else None)
            raise ConversionError(message) from (
                exc if isinstance(exc, Exception) else ConversionError(message)
            )

        options = DocumentRenderOptions(
            base_level=base_level,
            heading_level=resolve_heading_level(heading),
            drop_title=drop_title,
            numbered=numbered,
        )
        return cls(
            source_path=path,
            kind=InputKind.MARKDOWN,
            _html=rendered.html,
            _front_matter=rendered.front_matter,
            options=options,
        )

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
        callbacks: ConversionCallbacks | None = None,
    ) -> Document:
        """Create a document from an HTML file."""
        try:
            payload = path.read_text(encoding="utf-8")
        except OSError as exc:
            message = f"Failed to read HTML document '{path}': {exc}"
            if callbacks and callbacks.emit_error:
                callbacks.emit_error(message, exc)
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
                if callbacks and callbacks.emit_warning:
                    callbacks.emit_warning(message, exc)

        options = DocumentRenderOptions(
            base_level=base_level,
            heading_level=resolve_heading_level(heading),
            drop_title=drop_title,
            numbered=numbered,
        )
        return cls(
            source_path=path,
            kind=InputKind.HTML,
            _html=html,
            _front_matter={},
            options=options,
        )

    def copy(self) -> Document:
        """Return a deep copy of the document."""
        return Document(
            source_path=self.source_path,
            kind=self.kind,
            _html=self._html,
            _front_matter=copy.deepcopy(self._front_matter),
            options=self.options.copy(),
            slot_overrides=dict(self.slot_overrides),
            slot_inclusions=set(self.slot_inclusions),
        )

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
        if selector:
            self.slot_overrides[slot] = selector
        if include_document or (selector is None):
            self.slot_inclusions.add(slot)

    def to_context(self) -> DocumentContext:
        """Build a fresh DocumentContext for conversion."""
        return build_document_context(
            name=self.source_path.stem,
            source_path=self.source_path,
            html=self._html,
            front_matter=copy.deepcopy(self._front_matter),
            base_level=self.options.base_level,
            heading_level=self.options.heading_level,
            drop_title=self.options.drop_title,
            numbered=self.options.numbered,
        )
