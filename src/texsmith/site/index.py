"""The site on tmark: pre-pass, site label map and per-page lowering.

``specs/migration/web-profile.md`` §Recommendation, steps 1 and 2. Every
page is parsed with ``tmark.parse`` and resolved with ``numbering: "all"``
and a ``start`` chained from the previous page's ``next_start``, in
navigation order, so a reference on the first page reaches an item defined
on the last one and the numbers are continuous across the site. The
resolution of each page contributes its labels to the site map; lowering a
page (:meth:`SiteIndex.lower`) resolves it again with ``book`` = the site
map minus the page, then ``tmark.lower_web`` splices every TMark construct
into what Material renders and leaves every other byte alone. One thing is
printed from the metadata rather than from a span, since a node a pass
invented has no bytes to splice: the front matter's ``epigraph:``, which
:func:`~texsmith.passes.epigraph.splice_web` sets into the lowered text
where the ``epigraph`` pass sets its node into the block list.

A site generator hands the extension the body without its front matter
(MkDocs and Zensical both do), and the declarations made site-wide in the
generator's configuration are in no page at all. Both have to reach the
**parser**: ``press.declare.admonitions`` names the container kinds ``:::
exercise`` is spelled with, and a kind the parser does not know is
``container-unknown`` and stays literal text. So the page's own metadata,
with the site's declarations merged under it, is re-emitted as a YAML header
ahead of the body and the whole thing is parsed at once
(:func:`merge_declarations`, :func:`front_matter_text`).

That header is not what the rest of the pipeline speaks of: the text handed
to ``lower_web``, registered in the file table and named in every diagnostic
is the body padded with as many newlines as the front matter occupied in the
file, so a diagnostic reports the file's own line. :func:`move_spans` moves
every span of the parsed document from the one to the other and collapses
the synthetic front matter to the empty span at the top of the file. tmark
builds the typed keys itself, from the same YAML the page carried, so the
deprecated spellings (a top-level ``counters:``) keep working.

:class:`PageSource` and :func:`parse_page` are that reading, and they are
the *only* one: the book of :mod:`texsmith.site.book` parses its pages
through them too, rather than writing a merged copy somewhere and parsing
that. A page therefore reaches both media under its own path — a diagnostic
names the file the author edits, and an asset a page names relatively is
looked up from the page's own directory. What a book adds to a page, the
site's ``pymdownx.snippets`` ``auto_append`` and the abbreviation lines a
front-matter glossary declares, is an :class:`Appendix`: its bytes carry the
file that holds them, so a diagnostic in an appended definition names that
file and not a line past the end of the page.

Nothing here imports a site generator: :class:`SitePage` is all the index
asks of one, and a generator's own page object is converted at the call
site.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
import copy
from dataclasses import dataclass, field
import logging
from pathlib import Path, PurePosixPath
import posixpath
from typing import Any

import tmark
import yaml

from texsmith.core.documents import append_front_matter_abbreviations
from texsmith.core.front_matter import split_front_matter
from texsmith.diagnostics import (
    Diagnostic,
    DiagnosticEmitter,
    FileTable,
    LoggingEmitter,
    NullEmitter,
    SinkEmitter,
    from_tmark,
)
from texsmith.passes.epigraph import epigraph_of, insertion_index, splice_web
from texsmith.readers.loader import SearchPathLoader, TexsmithLoader
from texsmith.readers.tmark import parse_payload
from texsmith.site.config import language_from_mapping, site_declarations, web_options


__all__ = [
    "HEADING_PREFIXES",
    "SPAN_FIELDS",
    "Appendix",
    "LoweredPage",
    "PageRecord",
    "PageSource",
    "SiteIndex",
    "SitePage",
    "appendices_of",
    "front_matter_text",
    "merge_declarations",
    "move_spans",
    "page_declarations",
    "page_source",
    "parse_page",
    "site_index",
]

#: The predeclared series whose labels live on headings: a sibling link to
#: one of them shows the heading title (``sections: title``).
HEADING_PREFIXES = frozenset({"part", "chap", "sec", "app"})


@dataclass(frozen=True, slots=True)
class SitePage:
    """One page of the site, as little of it as the index needs.

    ``src_uri`` is the page's path relative to ``docs_dir`` in POSIX form
    (``guide/index.md``) — the identity a site generator gives a page and the
    name a diagnostic prints. ``meta`` is the page's front matter when the
    generator already parsed it; ``None`` asks the index to read the file.
    """

    src_uri: str
    abs_src_path: Path
    meta: Mapping[str, Any] | None = None


@dataclass(slots=True)
class PageRecord:
    """One page of the site as the pre-pass saw it."""

    src_uri: str
    abs_src_path: Path
    #: The page metadata (the YAML front matter).
    meta: dict[str, Any]
    #: Newlines the file holds, front matter included: what :meth:`padding`
    #: measures a body against.
    lines: int
    #: ``prefix -> first value`` this page was resolved with (the chain).
    start: dict[str, int] = field(default_factory=dict)
    #: ``prefix -> first free value`` after this page.
    next_start: dict[str, int] = field(default_factory=dict)
    #: This page's labels for its siblings (``location`` is ``src_uri#key``).
    labels: list[dict[str, Any]] = field(default_factory=list)
    #: The counters the page declares itself (either spelling).
    page_counters: dict[str, Any] = field(default_factory=dict)

    def padding(self, body: str) -> int:
        """Newlines to put ahead of ``body`` so it sits on the file's own lines.

        Measured against the body at hand rather than off the file's own
        split, because the two are not the same text: the splitters disagree
        on where a body starts (MkDocs' ``get_data`` eats the blank lines
        after the closing ``---``, :func:`split_front_matter` keeps them),
        and a generator's other plugins rewrite the Markdown besides.
        Counting the newlines that are missing is exact under either rule,
        and under an empty front matter (``---\\n---\\n``), which parses to no
        metadata at all yet still occupies two lines of the file.
        """
        return max(self.lines - body.count("\n"), 0)


@dataclass(slots=True)
class LoweredPage:
    """What :meth:`SiteIndex.lower` returns."""

    text: str
    diagnostics: list[Diagnostic]
    #: The ``References`` list when citations were lowered inline.
    bibliography: str | None = None


#: Every field of the IR schema holding a ``[file, start, end]``: a node's
#: own ``span``, the ``id_span`` of the attribute that named it and the
#: ``key_span`` of one item of a reference.
SPAN_FIELDS = frozenset({"span", "id_span", "key_span"})


#: What a span becomes: ``(start, end)`` in the parse input, ``[file, start,
#: end]`` in the files an author edits.
SpanLocator = Callable[[int, int], list[int]]


def _move_span(span: Any, locate: SpanLocator) -> Any:
    """One ``[file, start, end]`` moved onto the file its bytes came from."""
    if not (isinstance(span, list) and len(span) == 3):
        return span
    _file_id, start, end = span
    if not isinstance(start, int) or not isinstance(end, int):
        return span
    return locate(start, end)


def move_spans(value: Any, locate: SpanLocator) -> Any:
    """A parsed document with every span moved onto the file its bytes came from.

    The document is parsed from one text — a synthetic header, the page body,
    whatever the site appends to every page — and every consumer downstream
    (``tmark.lower_web``, the file table, the diagnostics) speaks of the
    files instead. ``locate`` answers, for a stretch of the parse input,
    which file holds those bytes and where; :meth:`PageSource.locate` is the
    one this module builds.
    """
    if isinstance(value, Mapping):
        moved: dict[str, Any] = {}
        for key, item in value.items():
            if key in SPAN_FIELDS:
                moved[key] = _move_span(item, locate)
            elif key == "related" and isinstance(item, list):
                moved[key] = [
                    [_move_span(pair[0], locate), *pair[1:]]
                    if isinstance(pair, list) and pair
                    else pair
                    for pair in item
                ]
            else:
                moved[key] = move_spans(item, locate)
        return moved
    if isinstance(value, list):
        return [move_spans(item, locate) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class Appendix:
    """Text added to the end of a page's source, and the file that holds it.

    A site gives every page a shared block by naming it under
    ``pymdownx.snippets``' ``auto_append`` — the acronym list, in practice —
    and a page's own ``press.declare.glossary`` declares acronyms the
    writers only print for a definition the document holds. Both land past
    the end of the page, where no line of the file can name them, so each
    stretch carries the file it belongs to: ``file`` is its id in the build's
    table and ``origin`` the byte of that file :attr:`text` starts at.
    ``origin`` is ``None`` for text no file holds — the lines a front-matter
    glossary synthesises — and a span landing there names the page's front
    matter instead.
    """

    #: What the parse input gains, its separator from the body included.
    text: str
    file: int
    origin: int | None


def appendices_of(
    paths: Iterable[Path],
    *,
    files: FileTable,
    display: Callable[[Path], str],
    logger: logging.Logger,
) -> tuple[Appendix, ...]:
    """The ``auto_append`` files of a site, read once and registered.

    Each file joins a page's source the way ``pymdownx.snippets`` appends it:
    a blank line, the file stripped of its outer blank lines, a newline. The
    file itself is what the table holds, under the name ``display`` gives it,
    so a diagnostic in one of those lines names the file at the line it is
    written on.
    """
    appendices: list[Appendix] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read the appended snippet '%s': %s", path, exc)
            continue
        content = text.strip()
        if not content:
            continue
        file_id = int(files.add(PurePosixPath(display(path)), text))
        # ``text`` opens with the blank line that separates the appendix from
        # the body, so the content starts two bytes into it.
        lead = len(text.encode("utf-8")) - len(text.lstrip().encode("utf-8"))
        appendices.append(Appendix(text=f"\n\n{content}\n", file=file_id, origin=lead - 2))
    return tuple(appendices)


@dataclass(frozen=True, slots=True)
class _Island:
    """A stretch of a parse input, from ``start`` up to the next island.

    ``delta`` is what a byte offset of the parse input gains to land in
    ``file``; ``None`` marks the stretches TeXSmith wrote itself — the
    re-emitted front matter, the abbreviation lines a glossary synthesises —
    which are in no file and collapse onto the page's own front matter.
    """

    start: int
    file: int
    delta: int | None


@dataclass(frozen=True, slots=True)
class PageSource:
    """A page as the parser reads it, and the files its bytes come from.

    :attr:`text` is what ``tmark.parse`` is handed: the merged front matter
    re-emitted as a YAML header, the page's body, then every
    :class:`Appendix`. Nothing downstream speaks of that text — the file
    table, the diagnostics and ``tmark.lower_web`` speak of the page itself
    and of each appended file under its own name — so :meth:`locate` maps a
    span of the one onto the others.

    :attr:`page_text` is what the page is registered as: its body padded with
    as many newlines as the front matter occupied in the file, so a span
    keeps the line it has in the file the author edits.
    """

    text: str
    page_text: str
    page_file: int
    islands: tuple[_Island, ...]

    def locate(self, start: int, end: int) -> list[int]:
        """Where the bytes ``[start, end)`` of :attr:`text` live in the files."""
        for island in reversed(self.islands):
            if start < island.start:
                continue
            if island.delta is None:
                break
            return [island.file, max(start + island.delta, 0), max(end + island.delta, 0)]
        # The synthetic front matter, and whatever TeXSmith appended out of
        # it: the empty span at the top of the page is where its metadata is.
        return [self.page_file, 0, 0]


def page_source(
    *,
    body: str,
    padding: int,
    meta: Mapping[str, Any],
    page_file: int,
    appendices: Sequence[Appendix] = (),
    abbreviations: bool = False,
    emitter: DiagnosticEmitter | None = None,
    logger: logging.Logger,
) -> PageSource:
    """Assemble what the parser reads for one page, and where its bytes belong.

    ``meta`` is the page's metadata with the site's declarations merged under
    it (:meth:`SiteIndex.merged_meta`): the parser learns a page's
    declarations from its front matter and from nowhere else — a container
    kind it does not know is ``container-unknown`` and stays literal text —
    so it is re-emitted as a header ahead of the body rather than attached to
    the parsed document afterwards.

    ``abbreviations`` synthesises the ``*[KEY]: description`` lines
    ``press.declare.glossary`` declares, which is what a writer needs to
    print an acronym and what the web, which shows the page's own bytes, must
    not gain.
    """
    header = front_matter_text(meta, logger=logger)
    header_bytes = len(header.encode("utf-8"))
    body_bytes = len(body.encode("utf-8"))
    islands = [
        _Island(start=0, file=page_file, delta=None),
        _Island(start=header_bytes, file=page_file, delta=padding - header_bytes),
    ]
    text = header + body
    offset = header_bytes + body_bytes
    for appendix in appendices:
        islands.append(
            _Island(
                start=offset,
                file=appendix.file,
                delta=None if appendix.origin is None else appendix.origin - offset,
            )
        )
        text += appendix.text
        offset += len(appendix.text.encode("utf-8"))
    if abbreviations:
        grown = append_front_matter_abbreviations(text, meta, emitter=emitter or NullEmitter())
        if grown != text:
            islands.append(_Island(start=offset, file=page_file, delta=None))
            text = grown
    return PageSource(
        text=text,
        page_text="\n" * padding + body,
        page_file=page_file,
        islands=tuple(islands),
    )


def parse_page(source: PageSource, *, name: str) -> dict[str, Any]:
    """``source`` parsed, with every span on the file its bytes came from.

    The deprecation of a front-matter key the merge wrote is dropped: the
    header is TeXSmith's spelling of the page's metadata, not the author's,
    and no one can fix in the page a key the page does not carry.
    """
    payload = parse_payload(source.text, file_id=source.page_file, name=name)
    payload = move_spans(payload, source.locate)
    payload["diagnostics"] = [
        item
        for item in payload.get("diagnostics") or ()
        if item.get("code") != "deprecated-frontmatter-key"
    ]
    return payload


def page_declarations(meta: Mapping[str, Any]) -> dict[str, Any]:
    """What a page declares itself: ``press.declare``, in either spelling.

    A kind (``counters``, ``admonitions``, ``glossary``…) maps to its own
    declarations; the deprecated top-level ``counters:`` joins them under
    ``counters``, so the two spellings merge with the site's instead of
    shadowing one another.
    """
    declared: dict[str, Any] = {}
    press = meta.get("press")
    if isinstance(press, Mapping):
        declare = press.get("declare")
        if isinstance(declare, Mapping):
            declared = {str(kind): value for kind, value in declare.items()}
    legacy = meta.get("counters")
    if isinstance(legacy, Mapping):
        counters = declared.get("counters")
        declared["counters"] = (
            {**counters, **legacy} if isinstance(counters, Mapping) else dict(legacy)
        )
    return declared


def _page_counter_declarations(meta: Mapping[str, Any]) -> dict[str, Any]:
    """The counters a page declares itself, in either spelling."""
    counters = page_declarations(meta).get("counters")
    return dict(counters) if isinstance(counters, Mapping) else {}


def merge_declarations(site: Mapping[str, Any], meta: Mapping[str, Any]) -> dict[str, Any]:
    """``meta`` with the site's ``press.declare`` merged under the page's own.

    The page wins kind by kind and key by key: a site-wide counter ``ex`` and
    a page-level counter ``fw`` both reach the parser, and a page redeclaring
    ``ex`` keeps its own. The site declares the same things a page does —
    counters, admonition kinds, glossary terms — so the merge is one level
    deep and knows none of the kinds by name.
    """
    merged = copy.deepcopy(dict(meta))
    merged.pop("counters", None)
    declare: dict[str, Any] = {}
    for source in (site, page_declarations(meta)):
        for kind, value in source.items():
            current = declare.get(kind)
            if isinstance(current, Mapping) and isinstance(value, Mapping):
                declare[kind] = {**current, **copy.deepcopy(dict(value))}
            else:
                declare[kind] = copy.deepcopy(value)
    if declare:
        press = merged.get("press")
        merged["press"] = (
            {**press, "declare": declare} if isinstance(press, Mapping) else {"declare": declare}
        )
    return merged


def front_matter_text(meta: Mapping[str, Any], *, logger: logging.Logger) -> str:
    """``meta`` as a YAML front-matter block; ``""`` when there is nothing to say."""
    if not meta:
        return ""
    try:
        body = yaml.safe_dump(dict(meta), sort_keys=False, allow_unicode=True)
    except yaml.YAMLError as exc:  # pragma: no cover - the metadata parsed once
        logger.warning("texsmith: cannot re-serialise the page metadata: %s", exc)
        return ""
    return f"---\n{body}---\n"


def site_index(
    options: Mapping[str, Any],
    *,
    project_dir: Path,
    theme: Any = None,
    site_language: Any = None,
    include_paths: Sequence[Path] = (),
    logger: logging.Logger | None = None,
    emitter: SinkEmitter | None = None,
) -> SiteIndex:
    """The index of a site, built from the ``texsmith`` options of its generator.

    The three integrations read those options from three places — MkDocs'
    validated plugin configuration, the ``texsmith:`` block of the file the
    Zensical extension reads, the same block ``texsmith site build`` reads —
    and ask the same three things of them: the site-wide declarations, the
    ``web:`` settings of the lowering, and the language, which is the
    plugin's own option before the site's (:func:`language_from_mapping`).
    One statement of that, so the media cannot answer it differently.
    """
    log = logger or logging.getLogger("texsmith.site")
    return SiteIndex(
        declare=site_declarations(options, logger=log),
        lang=options.get("language") or language_from_mapping(theme, site_language),
        web_options=web_options(options, logger=log),
        project_dir=project_dir,
        include_paths=include_paths,
        logger=log,
        emitter=emitter,
    )


class SiteIndex:
    """The pre-pass state of a site and the lowering of its pages."""

    def __init__(
        self,
        *,
        declare: Mapping[str, Any] | None = None,
        lang: str | None = None,
        web_options: Mapping[str, Any] | None = None,
        project_dir: Path | None = None,
        include_paths: Sequence[Path] = (),
        logger: logging.Logger | None = None,
        emitter: SinkEmitter | None = None,
    ) -> None:
        #: The site-wide ``press.declare`` of the generator's configuration,
        #: kind by kind, merged under each page's own declarations.
        self.declare: dict[str, Any] = dict(declare or {})
        self.lang = lang
        self.web_options: dict[str, Any] = dict(web_options or {})
        self.project_dir = project_dir
        #: Where a fence's ``include=`` is looked up when the page's own
        #: directory does not hold it: the site's ``pymdownx.snippets`` base
        #: path, which is what those paths are written against.
        self.include_paths: tuple[Path, ...] = tuple(include_paths)
        self._logger = logger or logging.getLogger("texsmith.site")
        # One emitter for the build: its sink owns the file table every page
        # registers in, so a page's ``span.file`` identifies it among the
        # others instead of being 0 in a table of its own.
        self.emitter = emitter if emitter is not None else LoggingEmitter(logger_obj=self._logger)
        # The lowering splices a fence's ``include=`` through this loader,
        # from the page's own path, then along the search path — the order
        # ``resolve_include`` follows for the PDF, through the same class.
        self.loader = SearchPathLoader(
            TexsmithLoader(self.emitter.sink.files, self.emitter.sink), self.include_paths
        )
        self._records: dict[str, PageRecord] = {}
        self._chain: dict[str, int] = {}

    # The pre-pass.

    @property
    def counters(self) -> Mapping[str, Any]:
        """The site-wide counter declarations, the one kind the book reads back."""
        counters = self.declare.get("counters")
        return counters if isinstance(counters, Mapping) else {}

    @property
    def records(self) -> Mapping[str, PageRecord]:
        return self._records

    def record(self, src_uri: str) -> PageRecord | None:
        return self._records.get(src_uri)

    def prepass(self, pages: Iterable[SitePage]) -> None:
        """Parse and resolve every page in the given order, chaining ``start``."""
        for page in pages:
            if page.src_uri in self._records:
                continue
            self.register(page)

    def register(self, page: SitePage) -> PageRecord | None:
        """Read one page, resolve it after the chain so far, keep its labels."""
        record = self.scan(page)
        if record is None:
            return None
        self._chain = dict(record.next_start)
        self._records[record.src_uri] = record
        return record

    def scan(self, page: SitePage) -> PageRecord | None:
        """Read one page and resolve it after the chain, without joining the site.

        :meth:`register` is this plus the two site-wide effects: the page's
        labels become part of the map every other page resolves against, and
        the numbering chain moves on to where the page left it. A page the
        site does not publish takes neither.
        """
        path = Path(page.abs_src_path)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            self._logger.warning("texsmith: could not pre-scan '%s': %s", page.src_uri, exc)
            return None
        file_meta, body = split_front_matter(text)
        meta = dict(page.meta) if page.meta is not None else file_meta
        record = PageRecord(
            src_uri=page.src_uri,
            abs_src_path=path,
            meta=meta,
            lines=text.count("\n"),
            start=dict(self._chain),
            page_counters=_page_counter_declarations(meta),
        )
        # The pre-pass reads the resolution and nothing else — no diagnostic of
        # it is reported — so the page is not registered in the file table
        # here: the lowering registers it, once, under the name it prints.
        source = self.page_source(record, body, page_file=0)
        doc = parse_page(source, name=self.display_path(path))
        resolved = tmark.resolve(doc, None, self._resolve_options(record))
        record.next_start = {
            str(prefix): int(value)
            for prefix, value in (resolved.get("next_start") or {}).items()
            if isinstance(value, int) and not isinstance(value, bool)
        }
        record.labels = [
            {**label, "location": f"{record.src_uri}#{label['key']}"}
            for label in resolved.get("book") or ()
        ]
        return record

    # The site map.

    def book_for(self, src_uri: str) -> list[dict[str, Any]]:
        """The site's labels minus the page's own, located relative to the page."""
        base = posixpath.dirname(src_uri)
        book: list[dict[str, Any]] = []
        for record in self._records.values():
            if record.src_uri == src_uri:
                continue
            target = posixpath.relpath(record.src_uri, base or ".")
            for label in record.labels:
                entry = dict(label)
                entry["location"] = f"{target}#{label['key']}"
                # tmark links a heading-hosted sibling by its title; a user
                # counter defined on a heading (``## T {#fw:x}``) is still
                # ``FW-03`` from another page.
                if entry.get("kind") == "header" and entry.get("prefix") not in HEADING_PREFIXES:
                    entry["kind"] = "counter_item"
                book.append(entry)
        return book

    # The lowering.

    def lower(self, page: SitePage, markdown: str) -> LoweredPage | None:
        """Resolve ``page`` against the site map, splice its constructs for the web."""
        record = self._records.get(page.src_uri)
        if record is None:
            # A page outside the navigation never went through the pre-pass:
            # it is lowered on its own, with the numbers that follow the last
            # page of the site, and its labels stay out of the site map.
            # Joining it there would make the map depend on the render order —
            # a page rendered before it would not see its labels and a page
            # rendered after it would.
            record = self.scan(page)
            if record is None:
                return None

        files = self.emitter.sink.files
        # ``src_uri`` is the generator's own path, always POSIX (unlike an
        # OS-native ``src_path``): registering it as a ``PurePosixPath`` keeps
        # a diagnostic's printed name identical on every OS, matching the
        # display name ``str()`` of a native ``Path`` would otherwise mangle
        # back to backslashes on Windows.
        display = record.src_uri
        file_id = int(files.add(PurePosixPath(display), "\n" * record.padding(markdown) + markdown))
        source = self.page_source(record, markdown, page_file=file_id)
        doc = parse_page(source, name=display)
        options = self._resolve_options(record)
        options["book"] = self.book_for(record.src_uri)
        resolved = tmark.resolve(doc, None, options)
        lowered = tmark.lower_web(source.page_text, doc, resolved, self.loader, self.web_options)

        # The padding the file table needed comes straight back off: a splice
        # never starts inside it, so the newlines are still there.
        text = lowered["text"]
        padding = record.padding(markdown)
        text = text[padding:] if text[:padding] == "\n" * padding else text.lstrip("\n")
        text = self._set_epigraph(text, doc)

        diagnostics = [
            from_tmark(item)
            for item in (
                *(doc.get("diagnostics") or ()),
                *(resolved.get("diagnostics") or ()),
                *(lowered.get("diagnostics") or ()),
            )
        ]
        return LoweredPage(
            text=text,
            diagnostics=diagnostics,
            bibliography=lowered.get("bibliography"),
        )

    @staticmethod
    def _set_epigraph(text: str, doc: Mapping[str, Any]) -> str:
        """The lowered text with the page's front-matter epigraph under its heading.

        The ``epigraph`` pass builds that quote as a node for the writers;
        ``tmark.lower_web`` splices a page's own bytes, and the node has
        none, so the web takes the lowered shape as text at the position
        :func:`~texsmith.passes.epigraph.insertion_index` gives it — the
        one statement of the rule, read here off the raw parse.
        """
        keys = (doc.get("front_matter") or {}).get("keys") or {}
        epigraph = epigraph_of(keys.get("epigraph"))
        if epigraph is None:
            return text
        blocks = doc.get("blocks") or ()
        return splice_web(text, epigraph, insertion_index(blocks[0]["type"] if blocks else None))

    def report(self, lowered: LoweredPage) -> None:
        """Log the diagnostics of a lowered page with ``path:line:col``."""
        for record in lowered.diagnostics:
            self.emitter.diagnostic(record)

    # Helpers.

    def display_path(self, path: Path) -> str:
        """``path`` as a diagnostic names it: relative to the project, in POSIX form."""
        if self.project_dir is not None:
            try:
                return path.resolve().relative_to(self.project_dir.resolve()).as_posix()
            except ValueError:
                pass
        return path.as_posix()

    def _resolve_options(self, record: PageRecord) -> dict[str, Any]:
        options: dict[str, Any] = {
            "path": str(record.abs_src_path),
            "numbering": "all",
        }
        if record.start:
            options["start"] = dict(record.start)
        if self.lang and not record.meta.get("lang"):
            options["lang"] = self.lang
        return options

    def merged_meta(self, meta: Mapping[str, Any]) -> dict[str, Any]:
        """A page's metadata with the site's declarations merged under it."""
        return merge_declarations(self.declare, meta)

    def page_source(
        self,
        record: PageRecord,
        body: str,
        *,
        page_file: int,
        appendices: Sequence[Appendix] = (),
        abbreviations: bool = False,
    ) -> PageSource:
        """What the parser reads for one page of this site.

        The site's declarations are merged under the page's own and re-emitted
        ahead of ``body`` (:func:`page_source`); the book calls this too, with
        the file's own body, the ``auto_append`` of the site and the
        abbreviation lines the writers need.
        """
        return page_source(
            body=body,
            padding=record.padding(body),
            meta=self.merged_meta(record.meta),
            page_file=page_file,
            appendices=appendices,
            abbreviations=abbreviations,
            emitter=self.emitter,
            logger=self._logger,
        )
