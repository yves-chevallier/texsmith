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
: Two readers feed the same shape during the TMark migration
  (``specs/migration/python-ir-and-passes.md`` §2). ``from_markdown`` with
  ``reader="html"`` (the default) keeps the Markdown → HTML path and its
  canonicalised HTML for the legacy writers; ``reader="tmark"`` parses the
  source with ``tmark.parse`` and ``from_html`` lowers an HTML page with the
  ``HtmlReader`` — both store the generated IR (:attr:`Document.ir`), the
  build's :class:`FileTable`, the reader diagnostics and, once the passes
  ran, the per-slot bodies, and render through the tmark writers. The
  ``front_matter`` mapping is the legacy view of the same YAML for both, so the
  template machinery does not change.

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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from texsmith.diagnostics import Diagnostic, FileTable
from texsmith.ir import model as irm
from texsmith.ir.walk import plain_text

from ..adapters.markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    MarkdownConversionError,
    render_markdown,
    split_front_matter,
)
from .conversion.debug import ConversionError, debug_enabled
from .conversion.inputs import (
    DOCUMENT_SELECTOR_SENTINEL,
    InputKind,
    SlotOptions,
    extract_content,
    extract_front_matter_slots,
)
from .diagnostics import DiagnosticEmitter, NullEmitter, use_emitter
from .heading_analysis import HeadingInspector, HeadingLevelScanner
from .metadata import PressMetadataError, normalise_press_metadata
from .templates.runtime import coerce_base_level


if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..passes.slots import SlotBody


__all__ = [
    "READERS",
    "Document",
    "SlotPlan",
    "TitleStrategy",
    "front_matter_has_title",
]

#: The readers ``from_markdown`` accepts (``--reader``).
READERS: tuple[str, ...] = ("html", "tmark")

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


def _coerce_document_base_level(value: int | str, emitter: DiagnosticEmitter) -> int:
    try:
        resolved = coerce_base_level(value, allow_none=False)
    except Exception as exc:  # pragma: no cover - defensive
        message = f"Invalid base level '{value}': {exc}"
        emitter.error(message, exc)
        raise ConversionError(message) from exc
    return int(resolved or 0)


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


def _append_front_matter_abbreviations(text: str, emitter: DiagnosticEmitter) -> str:
    """Append the ``*[KEY]: description`` lines of the front-matter glossary.

    ``press.declare.glossary.entries`` declares acronyms without writing an
    abbreviation definition for each; the legacy path synthesised those lines
    for ``markdown.abbr`` before rendering. The tmark reader does the same at
    the end of the source, where the appended lines move no existing span.
    """
    from .glossary import (
        GlossaryValidationError,
        append_synthetic_abbr_lines,
        parse_front_matter_glossary,
    )

    front_matter, _body = split_front_matter(text)
    try:
        glossary = parse_front_matter_glossary(front_matter)
    except GlossaryValidationError as exc:
        emitter.warning(str(exc))
        return text
    if glossary is None or not glossary.has_entries:
        return text
    return append_synthetic_abbr_lines(text, glossary)


@dataclass(slots=True)
class SlotPlan:
    """The slot requests of a document: selectors, wildcard inclusions, options.

    A view over the ``Document`` fields of the same names (the dictionaries are
    shared, not copied), so the slots pass and the legacy HTML splitter read
    one state.
    """

    selectors: dict[str, str]
    includes: set[str]
    options: dict[str, SlotOptions]
    requests: dict[str, str]


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
    slot_options: dict[str, SlotOptions] = field(default_factory=dict)
    extracted_title: str | None = None
    slot_requests: dict[str, str] = field(default_factory=dict)
    language: str | None = None
    bibliography: dict[str, Any] = field(default_factory=dict)
    #: ``"tmark"`` (``tmark.parse`` → :attr:`ir`) or ``"html"``: the ``HtmlReader``
    #: on an HTML input (→ :attr:`ir`), the legacy Markdown → HTML path otherwise.
    reader: str = "html"
    #: The IR of the source (``ir.file`` is its :attr:`files` id); ``None`` on the
    #: legacy path, which renders :attr:`html` through the Python writers.
    ir: irm.Document | None = None
    #: ``FileId -> SourceFile``; id 0 is the source, includes and loaded files follow.
    files: FileTable = field(default_factory=FileTable)
    #: Parse, pass, resolve and write records, in emission order.
    diagnostics: list[Diagnostic] = field(default_factory=list)
    #: The ``tmark.resolve`` result of the whole document (``handle`` included).
    resolved: dict[str, Any] | None = None
    #: The per-slot bodies computed by the ``slots``/``headings`` passes.
    bodies: tuple[SlotBody, ...] = ()
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
        reader: str = "html",
    ) -> Document:
        """Create a document from a Markdown file.

        ``reader="html"`` renders the Markdown to HTML (cached for reuse);
        ``reader="tmark"`` parses it with ``tmark.parse`` and keeps the IR.
        """
        if reader not in READERS:
            raise ValueError(f"Unknown reader '{reader}'; expected one of {', '.join(READERS)}")
        active_emitter = emitter or NullEmitter()

        if reader == "tmark":
            return cls._from_tmark(
                path,
                promote_title=promote_title,
                strip_heading=strip_heading,
                suppress_title=suppress_title,
                base_level=base_level,
                title_strategy=title_strategy,
                numbered=numbered,
                emitter=active_emitter,
            )

        # The counter and cross-reference extensions hold no emitter: they
        # report through the one installed here.
        try:
            with use_emitter(emitter):
                rendered = render_markdown(
                    path.read_text(encoding="utf-8"),
                    list(extensions or DEFAULT_MARKDOWN_EXTENSIONS),
                    base_path=path.parent,
                    document_path=path,
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
    def _from_tmark(
        cls,
        path: Path,
        *,
        promote_title: bool,
        strip_heading: bool,
        suppress_title: bool,
        base_level: int | str,
        title_strategy: TitleStrategy | None,
        numbered: bool,
        emitter: DiagnosticEmitter,
    ) -> Document:
        """Parse ``path`` with tmark; the parse diagnostics go to ``emitter`` and the document."""
        from ..readers import tmark as tmark_reader

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            message = f"Failed to read Markdown source '{path}': {exc}"
            emitter.error(message, exc)
            raise ConversionError(message) from exc

        # ``press.declare.glossary`` entries reach the body as the abbreviation
        # definitions the legacy path synthesised for ``markdown.abbr``: tmark
        # then lowers every occurrence to an ``Abbr`` and the writers to
        # ``\\tsacr{…}``. Appended at the end, so no span of the text above moves.
        text = _append_front_matter_abbreviations(text, emitter)

        # The build's file table is the emitter's when it has one, so every
        # diagnostic of the batch renders with its file name; a document then
        # takes the next free id (0 for the first one).
        files = getattr(emitter, "files", None)
        if not isinstance(files, FileTable):
            files = FileTable()
        file_id = files.add(path, text)
        ir_document, diagnostics = tmark_reader.read(text, file_id=file_id, name=str(path))
        for record in diagnostics:
            emitter.diagnostic(record)

        # The legacy mapping is the raw YAML, as the HTML path sees it:
        # ``normalise_press_metadata`` applies the same rules to both readers.
        front_matter, _body = split_front_matter(text)

        resolved_base_level = _coerce_document_base_level(base_level, emitter)
        declared_title = front_matter_has_title(front_matter)
        strategy = _resolve_title_strategy(
            explicit=title_strategy,
            promote_title=promote_title,
            strip_heading=strip_heading,
            has_declared_title=declared_title,
        )
        front_numbered = _front_matter_numbered(front_matter)
        document = cls(
            source_path=path,
            kind=InputKind.MARKDOWN,
            _html="",
            _front_matter=front_matter,
            base_level=resolved_base_level,
            title_strategy=strategy,
            numbered=numbered if front_numbered is None else front_numbered,
            suppress_title_metadata=suppress_title,
            reader="tmark",
            ir=ir_document,
            files=files,
            diagnostics=list(diagnostics),
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
        """Create a document from an HTML file, extracting only the renderable region.

        The fragment is lowered by the :class:`~texsmith.readers.html.HtmlReader`
        into the generated IR (:attr:`ir`); the document then takes the tmark
        writer path like a ``reader="tmark"`` Markdown source. The file enters
        the build's :class:`FileTable` with an empty text (no source spans).
        """
        from ..readers.html import HtmlReader

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
        files = getattr(active_emitter, "files", None)
        if not isinstance(files, FileTable):
            files = FileTable()
        file_id = files.add(path, "")
        reader = HtmlReader(diagnostics=active_emitter)
        ir_document = reader.read(html, file=file_id)
        document = cls(
            source_path=path,
            kind=InputKind.HTML,
            _html=html,
            _front_matter={},
            base_level=resolved_base_level,
            title_strategy=strategy,
            numbered=numbered,
            suppress_title_metadata=suppress_title,
            reader="html",
            ir=ir_document,
            files=files,
            diagnostics=list(reader.diagnostics),
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
            slot_options=dict(self.slot_options),
            extracted_title=None,
            slot_requests={},
            language=None,
            bibliography={},
            reader=self.reader,
            ir=self.ir,
            files=self.files,
            diagnostics=list(self.diagnostics),
        )

    def evolve(self, **changes: Any) -> Document:
        """A shallow copy with ``changes`` applied, prepared state kept.

        What a pass returns: the IR, the bodies or the resolution replaced, every
        other field (including the title decision of :meth:`prepare_for_conversion`)
        shared with the input, which is never mutated.
        """
        clone = copy.copy(self)
        for name, value in changes.items():
            setattr(clone, name, value)
        return clone

    @property
    def slots(self) -> SlotPlan:
        """The slot requests as one object (shared dictionaries, not copies)."""
        return SlotPlan(
            selectors=self.slot_selectors,
            includes=self.slot_includes,
            options=self.slot_options,
            requests=self.slot_requests,
        )

    @property
    def keys(self) -> irm.Keys:
        """The typed front matter of the tmark reader (empty on the HTML path)."""
        if self.ir is None:
            return irm.Keys()
        return self.ir.front_matter.keys

    @property
    def press(self) -> dict[str, Any]:
        """TeXSmith's validated press view of the front matter (``normalise_press_metadata``)."""
        payload = dict(self._front_matter)
        try:
            view = normalise_press_metadata(payload)
        except PressMetadataError:
            return {}
        return dict(view or {})

    def top_level_headers(self) -> list[irm.Header]:
        """The ``Header`` blocks at the root of the tmark IR, in order (empty on the HTML path)."""
        if self.ir is None:
            return []
        return [block for block in self.ir.blocks if isinstance(block, irm.Header)]

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
        self.slot_options = {}
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
            base_mapping, base_options = extract_front_matter_slots(payload)
            if base_mapping:
                selectors, includes = _split_slot_mapping(base_mapping)
                self.slot_selectors.update(selectors)
                self.slot_includes.update(includes)
            if base_options:
                self.slot_options.update(base_options)
        self._invalidate_prepared()

    @classmethod
    def _resolve_heading_alignment(cls, html: str, strategy: TitleStrategy) -> int:
        if strategy is not TitleStrategy.KEEP:
            return 0

        scanner = HeadingLevelScanner()
        try:
            scanner.feed(html)
        finally:
            scanner.close()

        minimum = scanner.minimum_level
        if minimum is None or minimum <= 1:
            return 0
        return minimum - 1

    def _extract_promoted_title(self) -> tuple[str | None, bool]:
        """Return the promoted title and whether the heading should be dropped."""
        if self.ir is not None:
            return self._extract_promoted_title_ir()
        inspector = HeadingInspector()
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

    def _extract_promoted_title_ir(self) -> tuple[str | None, bool]:
        """The IR twin of :meth:`_extract_promoted_title`: first top-level header, unique at its level."""
        headers = self.top_level_headers()
        if not headers:
            return None, False
        first = headers[0]
        if sum(1 for header in headers if header.level == first.level) != 1:
            return None, False
        text = plain_text(first.content).strip()
        return (text or None, bool(text))

    def _first_heading_level(self) -> int | None:
        """Return the level of the first heading in the document, if any."""
        if self.ir is not None:
            headers = self.top_level_headers()
            return headers[0].level if headers else None
        inspector = HeadingInspector()
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
        self.language = None
        self.bibliography = {}

    def promoted_title(self) -> str:
        """The title a leading unique top-level heading promotes to (``""`` when none).

        :meth:`prepare_for_conversion` records it in :attr:`extracted_title`
        for the LaTeX path, which calls it from ``resolve_conversion_context``.
        The Typst entry points get the document straight from
        ``prepare_documents``, before that runs, so they ask for the same
        decision here: the strategy must be ``PROMOTE_METADATA`` (the front
        matter declares no title), ``--no-title`` must not suppress it, and
        the heading must be the unique one at its level — the exact condition
        under which the ``title`` pass drops the heading from the body.
        """
        if self.extracted_title:
            return self.extracted_title
        if self.title_strategy is not TitleStrategy.PROMOTE_METADATA:
            return ""
        if self.suppress_title_metadata:
            return ""
        title, should_drop = self._extract_promoted_title()
        return title if title and should_drop else ""

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

        base_mapping, base_options = extract_front_matter_slots(metadata)
        base_selectors, base_includes = _split_slot_mapping(base_mapping)
        combined_selectors = dict(base_selectors)
        combined_selectors.update(self.slot_selectors)
        combined_includes = set(base_includes)
        combined_includes.update(self.slot_includes)
        combined_options = dict(base_options)
        combined_options.update(self.slot_options)

        self._front_matter = metadata
        self.slot_selectors = dict(combined_selectors)
        self.slot_includes = set(combined_includes)
        self.slot_options = dict(combined_options)
        self.slot_requests = _slot_request_mapping(combined_selectors, combined_includes)
        self.extracted_title = extracted_title
        self._prepared_drop_title = drop_title_flag
        self.language = None
        self.bibliography = {}
        return self
