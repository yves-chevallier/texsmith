"""The site on tmark: pre-pass, site label map and per-page lowering.

``specs/migration/web-profile.md`` §Recommendation, steps 1 and 2. Every
page is parsed with ``tmark.parse`` and resolved with ``numbering: "all"``
and a ``start`` chained from the previous page's ``next_start``, in
navigation order, so a reference on the first page reaches an item defined
on the last one and the numbers are continuous across the site. The
resolution of each page contributes its labels to the site map; lowering a
page (:meth:`SiteIndex.lower`) resolves it again with ``book`` = the site
map minus the page, then ``tmark.lower_web`` splices every TMark construct
into what Material renders and leaves every other byte alone.

MkDocs hands ``on_page_markdown`` the body without its front matter, and the
counters declared site-wide in ``mkdocs.yml`` are in no page at all. Rather
than re-injecting a YAML header (which shifts every line the diagnostics
name), the body is parsed as it is — padded with as many newlines as the
front matter occupied, so line numbers match the file — and the parsed
document receives a synthetic ``front_matter`` node whose typed keys are the
page's own metadata merged with the site declarations
(``press.declare.counters``). tmark builds the keys itself, from the same
YAML the page carried, so the deprecated spellings (a top-level
``counters:``) keep working.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import copy
from dataclasses import dataclass, field
import logging
from pathlib import Path
import posixpath
from typing import Any

from mkdocs.structure.pages import Page
from mkdocs.utils.meta import get_data
from texsmith.core.diagnostics import LoggingEmitter
from texsmith.diagnostics import Diagnostic, FileTable, from_tmark
import tmark
import yaml


__all__ = ["HEADING_PREFIXES", "LoweredPage", "PageRecord", "SiteIndex", "max_node_id"]

#: The predeclared series whose labels live on headings: a sibling link to
#: one of them shows the heading title (``sections: title``).
HEADING_PREFIXES = frozenset({"part", "chap", "sec", "app"})


@dataclass(slots=True)
class PageRecord:
    """One page of the site as the pre-pass saw it."""

    src_uri: str
    abs_src_path: Path
    #: The page metadata (the YAML front matter as MkDocs reads it).
    meta: dict[str, Any]
    #: The Markdown body: the file's at the pre-pass, the text MkDocs handed
    #: ``on_page_markdown`` (macros expanded) once the page was lowered.
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
    #: The diagnostics of the pre-pass front matter (an invalid declaration).
    front_matter_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    #: The counters the page declares itself (either spelling).
    page_counters: dict[str, Any] = field(default_factory=dict)
    lowered: bool = False


@dataclass(slots=True)
class LoweredPage:
    """What :meth:`SiteIndex.lower` returns."""

    text: str
    diagnostics: list[Diagnostic]
    files: FileTable
    #: The ``References`` list when citations were lowered inline.
    bibliography: str | None = None


def max_node_id(value: Any) -> int:
    """The largest ``id`` in a tmark JSON document (``0`` when none)."""
    best = 0
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "id" and isinstance(item, int) and not isinstance(item, bool):
                best = max(best, item)
            else:
                best = max(best, max_node_id(item))
    elif isinstance(value, list):
        for item in value:
            best = max(best, max_node_id(item))
    return best


def _page_counters(meta: Mapping[str, Any]) -> dict[str, Any]:
    """The counters a page declares, in either spelling."""
    declared: dict[str, Any] = {}
    press = meta.get("press")
    if isinstance(press, Mapping):
        declare = press.get("declare")
        if isinstance(declare, Mapping) and isinstance(
            declare.get("counters"), Mapping
        ):
            declared.update(declare["counters"])
    legacy = meta.get("counters")
    if isinstance(legacy, Mapping):
        declared.update(legacy)
    return declared


class SiteIndex:
    """The pre-pass state of a site and the lowering of its pages."""

    def __init__(
        self,
        *,
        counters: Mapping[str, Any] | None = None,
        lang: str | None = None,
        web_options: Mapping[str, Any] | None = None,
        project_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.counters: dict[str, Any] = dict(counters or {})
        self.lang = lang
        self.web_options: dict[str, Any] = dict(web_options or {})
        self.project_dir = project_dir
        self._logger = logger or logging.getLogger("mkdocs.plugins.texsmith")
        self._records: dict[str, PageRecord] = {}
        self._chain: dict[str, int] = {}

    # -- pre-pass ------------------------------------------------------------

    @property
    def records(self) -> Mapping[str, PageRecord]:
        return self._records

    def record(self, src_uri: str) -> PageRecord | None:
        return self._records.get(src_uri)

    def prepass(self, pages: Iterable[Page]) -> None:
        """Parse and resolve every page in the given order, chaining ``start``."""
        for page in pages:
            if page.file.src_uri in self._records:
                continue
            self.register(page)

    def register(self, page: Page) -> PageRecord | None:
        """Read one page, resolve it after the chain so far, keep its labels."""
        abs_src = getattr(page.file, "abs_src_path", None)
        if not abs_src:
            return None
        path = Path(abs_src)
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            self._logger.warning(
                "texsmith: could not pre-scan '%s': %s", page.file.src_uri, exc
            )
            return None
        body, meta = get_data(text)
        prefix = text[: len(text) - len(body)] if text.endswith(body) else ""
        record = PageRecord(
            src_uri=page.file.src_uri,
            abs_src_path=path,
            meta=dict(meta or {}),
            body=body,
            padding=prefix.count("\n"),
            start=dict(self._chain),
            page_counters=_page_counters(meta or {}),
        )
        padded = "\n" * record.padding + body
        doc = tmark.parse(padded, file=self._display_path(path))
        node, record.front_matter_diagnostics = self._front_matter_node(
            record.meta, file_id=0, node_id=max_node_id(doc) + 1
        )
        # ``front_matter: null`` is not a tmark document: a page with neither
        # metadata nor a site declaration keeps the node ``parse`` gave it.
        if node is not None:
            doc["front_matter"] = node
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

    # -- site map --------------------------------------------------------------

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
                if (
                    entry.get("kind") == "header"
                    and entry.get("prefix") not in HEADING_PREFIXES
                ):
                    entry["kind"] = "counter_item"
                book.append(entry)
        return book

    # -- lowering --------------------------------------------------------------

    def lower(self, page: Page, markdown: str) -> LoweredPage | None:
        """Resolve ``page`` against the site map, splice its constructs for Material."""
        record = self._records.get(page.file.src_uri)
        if record is None:
            # A page outside the navigation never went through the pre-pass:
            # it takes the numbers after the last page.
            record = self.register(page)
            if record is None:
                return None
        record.body = markdown
        record.lowered = True

        padded = "\n" * record.padding + markdown
        files = FileTable()
        display = self._display_path(record.abs_src_path)
        file_id = int(files.add(display, padded))
        doc = tmark.parse(padded, file=display, file_id=file_id)
        node, front_diagnostics = self._front_matter_node(
            record.meta, file_id=file_id, node_id=max_node_id(doc) + 1
        )
        if node is not None:
            doc["front_matter"] = node
        options = self._resolve_options(record)
        options["book"] = self.book_for(record.src_uri)
        resolved = tmark.resolve(doc, None, options)
        lowered = tmark.lower_web(padded, doc, resolved, None, self.web_options)

        text = lowered["text"]
        if text[: record.padding] == "\n" * record.padding:
            text = text[record.padding :]
        else:  # pragma: no cover - a splice never starts inside the padding
            text = text.lstrip("\n")

        diagnostics = [
            from_tmark(item)
            for item in (
                *(doc.get("diagnostics") or ()),
                *front_diagnostics,
                *(resolved.get("diagnostics") or ()),
                *(lowered.get("diagnostics") or ()),
            )
        ]
        return LoweredPage(
            text=text,
            diagnostics=diagnostics,
            files=files,
            bibliography=lowered.get("bibliography"),
        )

    def report(
        self, lowered: LoweredPage, *, emitter: LoggingEmitter | None = None
    ) -> None:
        """Log the diagnostics of a lowered page with ``path:line:col``."""
        if not lowered.diagnostics:
            return
        active = emitter or LoggingEmitter(logger_obj=self._logger, files=lowered.files)
        for record in lowered.diagnostics:
            active.diagnostic(record)

    # -- helpers ---------------------------------------------------------------

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

    def _front_matter_node(
        self, meta: Mapping[str, Any], *, file_id: int, node_id: int
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """A ``front_matter`` node carrying ``meta`` plus the site declarations.

        Built by tmark from the YAML MkDocs read, so its ``keys`` are the
        typed ones (``press.declare.counters``, ``lang``, …) and the page's
        deprecated spellings are honoured; the site-wide counters are merged
        under the page's own. ``None`` when there is nothing to declare.
        """
        merged: dict[str, Any] = copy.deepcopy(dict(meta))
        counters = {**self.counters, **_page_counters(meta)}
        merged.pop("counters", None)
        if counters:
            press = merged.get("press")
            if not isinstance(press, dict):
                press = {}
                merged["press"] = press
            declare = press.get("declare")
            if not isinstance(declare, dict):
                declare = {}
                press["declare"] = declare
            declare["counters"] = counters
        if not merged:
            return None, []
        try:
            header = (
                "---\n"
                + yaml.safe_dump(merged, sort_keys=False, allow_unicode=True)
                + "---\n"
            )
        except yaml.YAMLError as exc:  # pragma: no cover - MkDocs already loaded it
            self._logger.warning(
                "texsmith: cannot re-serialise the page metadata: %s", exc
            )
            return None, []
        parsed = tmark.parse(header)
        node = parsed.get("front_matter")
        if not isinstance(node, dict):
            return None, []
        node["id"] = node_id
        node["span"] = [file_id, 0, 0]
        node["raw"] = ""
        diagnostics = [
            {**item, "span": [file_id, 0, 0]}
            for item in parsed.get("diagnostics") or ()
            if item.get("code") != "deprecated-frontmatter-key"
        ]
        return node, diagnostics
