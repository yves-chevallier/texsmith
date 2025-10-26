"""High-level document abstractions used by the TeXSmith public API."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..conversion import (
    ConversionCallbacks,
    ConversionError,
    DocumentContext,
    InputKind,
    build_document_context,
    extract_content,
)
from ..markdown import DEFAULT_MARKDOWN_EXTENSIONS, MarkdownConversionError, render_markdown
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
    def from_label(cls, value: str | int | "HeadingLevel") -> "HeadingLevel":
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

    def copy(self) -> "DocumentRenderOptions":
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
    ) -> "Document":
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
            raise ConversionError(message) from exc if isinstance(exc, Exception) else ConversionError(
                message
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
    ) -> "Document":
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

    def copy(self) -> "Document":
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
        return self.options.drop_title

    @drop_title.setter
    def drop_title(self, value: bool) -> None:
        self.options.drop_title = bool(value)

    @property
    def numbered(self) -> bool:
        return self.options.numbered

    @numbered.setter
    def numbered(self, value: bool) -> None:
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
