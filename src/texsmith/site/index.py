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
file, so a diagnostic reports the file's own line. :func:`shift_spans` moves
every span of the parsed document from the one to the other — by the padding
minus the header, in bytes — and collapses the synthetic front matter to the
empty span at the top of the file. tmark builds the typed keys itself, from
the same YAML the page carried, so the deprecated spellings (a top-level
``counters:``) keep working.

Nothing here imports a site generator: :class:`SitePage` is all the index
asks of one, and a generator's own page object is converted at the call
site.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import copy
from dataclasses import dataclass, field
import logging
from pathlib import Path, PurePosixPath
import posixpath
from typing import Any

import tmark
import yaml

from texsmith.core.front_matter import split_front_matter
from texsmith.diagnostics import Diagnostic, LoggingEmitter, SinkEmitter, from_tmark
from texsmith.passes.epigraph import epigraph_of, insertion_index, splice_web
from texsmith.readers.loader import SearchPathLoader, TexsmithLoader


__all__ = [
    "HEADING_PREFIXES",
    "SPAN_FIELDS",
    "LoweredPage",
    "PageRecord",
    "SiteIndex",
    "SitePage",
    "front_matter_text",
    "merge_declarations",
    "page_declarations",
    "shift_spans",
    "split_page",
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
    #: The Markdown body: the file's at the pre-pass, the text the generator
    #: handed the extension (macros expanded) once the page was lowered.
    body: str
    #: Lines the front matter occupied in the file, so a padded body keeps
    #: the file's line numbers.
    padding: int
    #: ``prefix -> first value`` this page was resolved with (the chain).
    start: dict[str, int] = field(default_factory=dict)
    #: ``prefix -> first free value`` after this page.
    next_start: dict[str, int] = field(default_factory=dict)
    #: This page's labels for its siblings (``location`` is ``src_uri#key``).
    labels: list[dict[str, Any]] = field(default_factory=list)
    #: The counters the page declares itself (either spelling).
    page_counters: dict[str, Any] = field(default_factory=dict)
    lowered: bool = False


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


def _shift_span(span: Any, delta: int, empty_file: int) -> Any:
    """One ``[file, start, end]`` moved by ``delta``; the header collapses to nothing."""
    if not (isinstance(span, list) and len(span) == 3):
        return span
    file_id, start, end = span
    if not isinstance(start, int) or not isinstance(end, int):
        return span
    if start + delta < 0:
        # The span sits in the synthetic header, which is in no file: the
        # empty span at the top of the page is where its front matter is.
        return [empty_file, 0, 0]
    return [file_id, start + delta, end + delta]


def shift_spans(value: Any, delta: int, *, empty_file: int = 0) -> Any:
    """A parsed document with every span moved by ``delta`` bytes.

    The document is parsed from a synthetic header followed by the page
    body, and every consumer downstream — ``tmark.lower_web``, the file
    table, the diagnostics — speaks of the padded body instead. One shift
    puts the whole tree in that second text's coordinates; a span that would
    land before its start belongs to the header and collapses to the empty
    span at the top of ``empty_file``.
    """
    if delta == 0:
        return value
    if isinstance(value, Mapping):
        shifted: dict[str, Any] = {}
        for key, item in value.items():
            if key in SPAN_FIELDS:
                shifted[key] = _shift_span(item, delta, empty_file)
            elif key == "related" and isinstance(item, list):
                shifted[key] = [
                    [_shift_span(pair[0], delta, empty_file), *pair[1:]]
                    if isinstance(pair, list) and pair
                    else pair
                    for pair in item
                ]
            else:
                shifted[key] = shift_spans(item, delta, empty_file=empty_file)
        return shifted
    if isinstance(value, list):
        return [shift_spans(item, delta, empty_file=empty_file) for item in value]
    return value


def split_page(text: str) -> tuple[dict[str, Any], str, int]:
    """The page's front matter, its body, and the lines the front matter took.

    The padding is read off the *original* text — the newlines it holds minus
    the ones the body still holds — instead of measuring the prefix a splitter
    returns, because the splitters disagree on what the prefix is:
    :func:`~texsmith.core.front_matter.split_front_matter` keeps the blank
    lines that follow the closing ``---`` and normalises CRLF, where MkDocs's
    ``get_data`` strips those blank lines with the front matter. Counting the
    newlines that are gone is exact under either rule, and under an empty
    front matter (``---\\n---\\n``), which parses to no metadata at all yet
    still occupies two lines of the file.
    """
    meta, body = split_front_matter(text)
    return meta, body, text.count("\n") - body.count("\n")


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
        path = Path(page.abs_src_path)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            self._logger.warning("texsmith: could not pre-scan '%s': %s", page.src_uri, exc)
            return None
        file_meta, body, padding = split_page(text)
        meta = dict(page.meta) if page.meta is not None else file_meta
        record = PageRecord(
            src_uri=page.src_uri,
            abs_src_path=path,
            meta=meta,
            body=body,
            padding=padding,
            start=dict(self._chain),
            page_counters=_page_counter_declarations(meta),
        )
        doc, _padded = self._parse_page(record, body, file=self._display_path(path), file_id=0)
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
        self._chain = dict(record.next_start)
        self._records[record.src_uri] = record
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
            # it takes the numbers after the last page.
            record = self.register(page)
            if record is None:
                return None
        record.body = markdown
        record.lowered = True

        files = self.emitter.sink.files
        # ``src_uri`` is the generator's own path, always POSIX (unlike an
        # OS-native ``src_path``): registering it as a ``PurePosixPath`` keeps
        # a diagnostic's printed name identical on every OS, matching the
        # display name ``str()`` of a native ``Path`` would otherwise mangle
        # back to backslashes on Windows.
        display = record.src_uri
        padded = "\n" * record.padding + markdown
        file_id = int(files.add(PurePosixPath(display), padded))
        doc, padded = self._parse_page(record, markdown, file=display, file_id=file_id)
        options = self._resolve_options(record)
        options["book"] = self.book_for(record.src_uri)
        resolved = tmark.resolve(doc, None, options)
        lowered = tmark.lower_web(padded, doc, resolved, self.loader, self.web_options)

        text = lowered["text"]
        if text[: record.padding] == "\n" * record.padding:
            text = text[record.padding :]
        else:  # pragma: no cover - a splice never starts inside the padding
            text = text.lstrip("\n")
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

    def _display_path(self, path: Path) -> str:
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

    def _parse_page(
        self, record: PageRecord, body: str, *, file: str, file_id: int
    ) -> tuple[dict[str, Any], str]:
        """``(doc, padded)``: the page parsed with its declarations in front of it.

        The parser learns a page's declarations from its front matter and
        from nowhere else — a container kind it does not know is
        ``container-unknown`` and stays literal — so the merged metadata is
        re-emitted as a header and parsed with the body. The document then
        moves to the coordinates of ``padded``, the text every consumer
        downstream reads, where the body sits on the file's own lines.
        """
        header = front_matter_text(self.merged_meta(record.meta), logger=self._logger)
        padded = "\n" * record.padding + body
        doc = tmark.parse(header + body, file=file, file_id=file_id)
        doc = shift_spans(doc, record.padding - len(header.encode("utf-8")), empty_file=file_id)
        # The header is TeXSmith's spelling of the page's metadata, not the
        # author's: a deprecation it triggers names a key the merge wrote,
        # which no one can fix in the page.
        doc["diagnostics"] = [
            item
            for item in doc.get("diagnostics") or ()
            if item.get("code") != "deprecated-frontmatter-key"
        ]
        return doc, padded
