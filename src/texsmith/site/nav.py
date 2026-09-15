"""Resolve the documentation navigation without MkDocs.

Zensical reimplements ``mkdocs-awesome-nav`` in Rust and never hands the
resolved navigation back to Python, so TeXSmith resolves it itself. Two things
depend on the answer: the order in which the site's pages are pre-passed (so
counters and cross-references number continuously across the site) and the
chapter order and section titles of the PDF book built from the site.

The resolver reproduces three behaviours, in this order of precedence:

1. ``.nav.yml`` files, as ``mkdocs-awesome-nav`` reads them;
2. a plain MkDocs ``nav:`` list, when the configuration has one and the
   documentation tree carries no ``.nav.yml``;
3. MkDocs' default navigation — every page, nested by directory, index first.

Neither ``mkdocs`` nor ``mkdocs_awesome_nav`` is imported: under Zensical both
are absent. The globbing, the natural sort, the gitignore matching of
``exclude_docs`` and the page-title rules are therefore reimplemented here,
faithfully enough that ``pages()`` equals the page list of a real MkDocs build
(``tests/test_site_nav.py`` pins that against a recorded fixture).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
import logging
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml

from texsmith.core.front_matter import split_front_matter


__all__ = [
    "NavItem",
    "NavLink",
    "NavPage",
    "NavSection",
    "Navigation",
    "page_title",
    "resolve_navigation",
]

logger = logging.getLogger(__name__)

NAV_CONFIG_FILENAME = ".nav.yml"
"""The per-directory configuration file ``mkdocs-awesome-nav`` reads."""

MARKDOWN_SUFFIXES = (".markdown", ".mdown", ".mkdn", ".mkd", ".md")
"""The extensions MkDocs treats as documentation pages."""

INDEX_STEMS = ("index", "README")
"""Filenames MkDocs turns into the directory's own page."""

DEFAULT_EXCLUDED = (".*", "/templates/")
"""MkDocs' built-in ``exclude_docs`` patterns."""

_DEFAULT_NAV_GLOBS = ("@(index.md|README.md)", "*")
"""The implicit nav of a directory without a ``.nav.yml``: index first, then all."""


@dataclass(frozen=True, slots=True)
class NavPage:
    """A documentation page reached by the navigation."""

    title: str | None
    """The title the navigation gives the page, or ``None`` to infer it."""

    src_uri: str
    """The page's POSIX path relative to ``docs_dir``, e.g. ``guide/index.md``."""

    abs_path: Path
    """The page's absolute path on disk."""


@dataclass(frozen=True, slots=True)
class NavLink:
    """An external link listed in the navigation."""

    title: str
    url: str


@dataclass(frozen=True, slots=True)
class NavSection:
    """A group of navigation items, with the page that stands for the group."""

    title: str
    children: tuple[NavItem, ...]
    index: NavPage | None = None
    """The section's index page, when its first child is an ``index.md``."""


NavItem = NavPage | NavSection | NavLink
"""What a navigation holds: pages, sections and links."""


@dataclass(frozen=True, slots=True)
class Navigation:
    """The resolved navigation of a documentation tree."""

    items: tuple[NavItem, ...]
    _unlisted: tuple[NavPage, ...] = ()

    def pages(self) -> Iterator[NavPage]:
        """Yield the navigation's pages depth-first, section index first."""
        yield from _iter_pages(self.items)

    def unlisted(self) -> tuple[NavPage, ...]:
        """Return the pages the navigation does not reach, in file order."""
        return self._unlisted


def resolve_navigation(
    docs_dir: Path,
    nav: list[Any] | None = None,
    *,
    exclude_docs: str | None = None,
) -> Navigation:
    """Resolve the navigation of ``docs_dir``.

    Args:
        docs_dir: The documentation root, MkDocs' ``docs_dir``.
        nav: A plain MkDocs ``nav:`` list, used when no ``.nav.yml`` exists.
        exclude_docs: MkDocs' ``exclude_docs``, gitignore patterns one per line.

    Returns:
        The navigation, plus the pages it leaves out.
    """
    docs_dir = Path(docs_dir)
    excluder = _GitIgnoreSpec.from_text(exclude_docs, defaults=DEFAULT_EXCLUDED)
    every_page = _collect_pages(docs_dir)
    pages = [path for path in every_page if not excluder.match(path.as_posix())]

    if _has_nav_config(docs_dir):
        items = _resolve_awesome_nav(docs_dir, pages)
    elif nav is not None:
        items = _resolve_mkdocs_nav(nav, docs_dir, every_page)
    else:
        items = _default_nav(docs_dir, pages)

    reached = {page.src_uri for page in _iter_pages(items)}
    unlisted = tuple(
        NavPage(None, path.as_posix(), docs_dir / path)
        for path in pages
        if path.as_posix() not in reached
    )
    return Navigation(items, unlisted)


def page_title(page: NavPage) -> str:
    """Return the title of ``page``, the way MkDocs computes it.

    The navigation's own title wins, then the front matter ``title``, then the
    first level-one heading of the file. A page without any of those is named
    after its file — an ``index.md`` after the directory that holds it, and the
    root ``index.md`` "Home", as MkDocs names its homepage.
    """
    if page.title:
        return page.title

    source = _read_text(page.abs_path)
    metadata, body = split_front_matter(source)
    declared = metadata.get("title")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()

    heading = _first_heading(body)
    if heading:
        return heading

    src_uri = PurePosixPath(page.src_uri)
    if src_uri.stem in INDEX_STEMS:
        parent = src_uri.parent
        if parent == PurePosixPath("."):
            return "Home"
        return _dirname_to_title(parent.name)
    return _dirname_to_title(src_uri.stem)


def _iter_pages(items: Iterable[NavItem]) -> Iterator[NavPage]:
    """Walk ``items`` depth-first, yielding each section's index page first."""
    for item in items:
        if isinstance(item, NavPage):
            yield item
        elif isinstance(item, NavSection):
            if item.index is not None:
                yield item.index
            yield from _iter_pages(item.children)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        logger.warning("Cannot read %s", path)
        return ""


_ATX_HEADING = re.compile(r"^#[ \t]+(?P<text>.+?)[ \t]*#*[ \t]*$")
_SETEXT_UNDERLINE = re.compile(r"^=+[ \t]*$")
_HEADING_ATTRIBUTES = re.compile(r"[ \t]*\{[^{}]*\}$")


def _first_heading(markdown: str) -> str | None:
    """Return the text of a level-one heading opening the document.

    MkDocs takes the page title from the first element of the rendered page,
    and only when that element is an ``h1``: a page opening with an anchor, a
    paragraph or an admonition is named after its file instead, whatever
    headings come later.
    """
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        atx = _ATX_HEADING.match(line)
        if atx is not None:
            return _HEADING_ATTRIBUTES.sub("", atx.group("text")).strip() or None
        underline = lines[index + 1] if index + 1 < len(lines) else ""
        if _SETEXT_UNDERLINE.match(underline):
            return _HEADING_ATTRIBUTES.sub("", line).strip() or None
        return None
    return None


def _dirname_to_title(name: str) -> str:
    """Humanise a file or directory name, the way MkDocs does."""
    title = name.replace("-", " ").replace("_", " ")
    if title.lower() == title:
        title = title.capitalize()
    return title


def _collect_pages(docs_dir: Path) -> list[PurePosixPath]:
    """List the documentation pages of ``docs_dir`` in MkDocs' file order."""
    pages: list[PurePosixPath] = []

    def walk(directory: Path, prefix: str) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError:
            logger.warning("Cannot list %s", directory)
            return
        files = [entry for entry in entries if entry.is_file()]
        directories = [entry for entry in entries if entry.is_dir()]
        names = sorted(
            (entry.name for entry in files if entry.suffix in MARKDOWN_SUFFIXES),
            key=_filename_sort_key,
        )
        if len(names) > 1 and names[0] == "README.md" and names[1] == "index.md":
            # MkDocs drops README.md when index.md claims the same URL.
            names.pop(0)
        pages.extend(PurePosixPath(prefix + name) for name in names)
        for entry in directories:
            walk(entry, f"{prefix}{entry.name}/")

    walk(docs_dir, "")
    return pages


def _filename_sort_key(name: str) -> tuple[bool, str]:
    """Sort ``index`` and ``README`` first, then by filename, as MkDocs does."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return (stem not in INDEX_STEMS, name)


def _has_nav_config(docs_dir: Path) -> bool:
    return next(docs_dir.rglob(NAV_CONFIG_FILENAME), None) is not None


# Glob patterns, as wcmatch matches them for mkdocs-awesome-nav


_EXTGLOB_PREFIXES = "?*+@!"


_SEGMENT = "[^/]+"
_DOTLESS_SEGMENT = r"(?!\.)[^/]+"


@dataclass(frozen=True, slots=True)
class _Glob:
    """A compiled navigation glob, matched against a path relative to the docs."""

    file_regex: re.Pattern[str]
    directory_regex: re.Pattern[str]
    directories_only: bool

    def match(self, subject: str) -> bool:
        """Match ``subject``, a POSIX path with a trailing slash for directories."""
        is_directory = subject.endswith("/")
        if self.directories_only and not is_directory:
            return False
        regex = self.directory_regex if is_directory else self.file_regex
        return regex.match(subject.removesuffix("/")) is not None


def _compile_glob(pattern: str) -> _Glob:
    """Compile a ``*``/``**``/``?``/``[…]``/``@(…)`` pattern anchored at the docs root.

    A trailing slash restricts the pattern to directories, and, as in a shell,
    a wildcard never matches a leading dot.
    """
    directories_only = pattern.endswith("/")
    body = pattern.removesuffix("/")
    return _Glob(
        re.compile(_translate_glob(body, dot_rule=True) + "$"),
        re.compile(_translate_glob(body, dot_rule=True, directory_subject=True) + "$"),
        directories_only,
    )


def _translate_glob(pattern: str, *, dot_rule: bool, directory_subject: bool = False) -> str:
    """Translate a glob into a regular expression over a path without a trailing slash.

    ``directory_subject`` lets a trailing ``**`` match nothing at all, so that
    ``guide/**`` matches the ``guide`` directory itself, as wcmatch does.
    """
    any_segment = _DOTLESS_SEGMENT if dot_rule else _SEGMENT
    segments = pattern.split("/")
    parts: list[str] = []
    separator = ""
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            if not last:
                parts.append(f"{separator}(?:{any_segment}/)*")
                separator = ""
            elif separator:
                repeat = "*" if directory_subject else "+"
                parts.append(f"(?:/{any_segment}){repeat}")
            else:
                parts.append(f"{any_segment}(?:/{any_segment})*")
            continue
        parts.append(separator + _translate_segment(segment, dot_rule=dot_rule))
        separator = "/"
    return "".join(parts)


def _translate_segment(segment: str, *, dot_rule: bool = False) -> str:
    """Translate one path segment of a glob into a regular expression."""
    out: list[str] = []
    if dot_rule and not segment.startswith("."):
        out.append(r"(?!\.)")
    index = 0
    length = len(segment)
    while index < length:
        char = segment[index]
        if char in _EXTGLOB_PREFIXES and segment[index + 1 : index + 2] == "(":
            body, index = _read_group(segment, index + 2)
            alternatives = "|".join(
                _translate_segment(alternative) for alternative in _split_alternatives(body)
            )
            if char == "!":
                rest = _translate_segment(segment[index:])
                negative = f"(?:(?!(?:{alternatives}){rest}(?:/|$))[^/]*)"
                return "".join(out) + negative + rest
            quantifier = {"?": "?", "*": "*", "+": "+", "@": ""}[char]
            out.append(f"(?:{alternatives}){quantifier}")
            continue
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            character_class, index = _read_character_class(segment, index)
            out.append(character_class)
            continue
        elif char == "\\" and index + 1 < length:
            out.append(re.escape(segment[index + 1]))
            index += 2
            continue
        else:
            out.append(re.escape(char))
        index += 1
    return "".join(out)


def _read_group(pattern: str, start: int) -> tuple[str, int]:
    """Read a parenthesised extglob body, returning it and the index after it."""
    depth = 1
    index = start
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return pattern[start:index], index + 1
        index += 1
    return pattern[start:], len(pattern)


def _split_alternatives(body: str) -> list[str]:
    alternatives: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            alternatives.append("".join(current))
            current = []
            continue
        current.append(char)
    alternatives.append("".join(current))
    return alternatives


def _read_character_class(pattern: str, start: int) -> tuple[str, int]:
    """Read a ``[…]`` class, returning its regular expression and the next index."""
    index = start + 1
    negated = pattern[index : index + 1] in ("!", "^")
    if negated:
        index += 1
    if pattern[index : index + 1] == "]":
        index += 1
    while index < len(pattern) and pattern[index] != "]":
        index += 1
    if index >= len(pattern):
        return re.escape("["), start + 1
    body = pattern[start + 1 : index]
    if negated:
        body = "^" + body[1:]
    return f"[{body.replace('/', '')}]", index + 1


def _absolute_pattern(path: PurePosixPath, pattern: str) -> str:
    """Anchor ``pattern`` at ``path``, keeping the directory-only trailing slash."""
    return (path / pattern).as_posix() + ("/" if pattern.endswith("/") else "")


# exclude_docs, as pathspec matches gitignore patterns for MkDocs


@dataclass(frozen=True, slots=True)
class _GitIgnoreSpec:
    """A gitignore-style list of patterns, last match winning."""

    patterns: tuple[tuple[re.Pattern[str], bool], ...] = ()

    @staticmethod
    def from_text(text: str | None, *, defaults: Sequence[str] = ()) -> _GitIgnoreSpec:
        lines = list(defaults) + (text.splitlines() if text else [])
        patterns = [_compile_gitignore(line) for line in lines]
        return _GitIgnoreSpec(tuple(pattern for pattern in patterns if pattern is not None))

    def match(self, path: str) -> bool:
        matched = False
        for regex, negated in self.patterns:
            if regex.match(path) is not None:
                matched = not negated
        return matched


def _compile_gitignore(line: str) -> tuple[re.Pattern[str], bool] | None:
    pattern = line.strip()
    if not pattern or pattern.startswith("#"):
        return None
    negated = pattern.startswith("!")
    if negated or pattern.startswith("\\"):
        pattern = pattern[1:]
    directories_only = pattern.endswith("/")
    body = pattern.rstrip("/")
    if not body:
        return None
    if body.startswith("/"):
        anchored = True
        body = body.lstrip("/")
    else:
        anchored = "/" in body
    prefix = "" if anchored else "(?:.*/)?"
    suffix = "/.*" if directories_only else "(?:/.*)?"
    return re.compile(prefix + _translate_glob(body, dot_rule=False) + suffix + "$"), negated


# Sorting, as natsort orders the matches of a nav pattern


@dataclass(frozen=True, slots=True)
class _SortConfig:
    """``sort:`` as ``mkdocs-awesome-nav`` resolves it, defaults included."""

    by: str = "path"
    direction: str = "asc"
    type: str = "natural"
    sections: str = "last"
    ignore_case: bool = False


_DIGITS = re.compile(r"(\d+)")


def _chunk_key(text: str, *, ignore_case: bool) -> tuple[str | int, ...]:
    """Split ``text`` into alternating text and number chunks, letters grouped."""
    tokens = _DIGITS.split(text.casefold() if ignore_case else text)
    while len(tokens) > 1 and tokens[-1] == "":
        tokens.pop()
    return tuple(
        int(token) if position % 2 else _group_letters(token)
        for position, token in enumerate(tokens)
    )


def _group_letters(text: str) -> str:
    """Interleave each character with its casefolded form, as natsort does."""
    return "".join(character.casefold() + character for character in text)


def _path_components(value: str) -> tuple[str, ...]:
    """Split a path into directories, the stem and each suffix, as natsort does."""
    parts = [part for part in value.split("/") if part not in ("", ".")]
    if not parts:
        return (value,)
    base = PurePosixPath(parts[-1])
    suffixes = base.suffixes
    stem = parts[-1][: len(parts[-1]) - sum(len(suffix) for suffix in suffixes)]
    return (*parts[:-1], stem, *suffixes)


def _natural_key(value: str, *, split_path: bool, ignore_case: bool) -> tuple[Any, ...]:
    components = _path_components(value) if split_path else (value,)
    return tuple(_chunk_key(component, ignore_case=ignore_case) for component in components)


def _sort_key(value: str | tuple[str, ...], sort: _SortConfig) -> Any:
    if isinstance(value, tuple):
        return tuple(_sort_key(item, sort) for item in value)
    if sort.type == "natural":
        return _natural_key(value, split_path=sort.by != "title", ignore_case=sort.ignore_case)
    return value.casefold() if sort.ignore_case else value


# The navigation tree, as mkdocs-awesome-nav resolves it


@dataclass(frozen=True, slots=True)
class _Entry:
    """A page or a directory of the documentation tree."""

    path: PurePosixPath
    abs_path: Path
    is_dir: bool

    @property
    def subject(self) -> str:
        """The path a glob is matched against: directories carry a trailing slash."""
        return self.path.as_posix() + ("/" if self.is_dir else "")


class _Context:
    """The pages and directories a navigation can still claim."""

    def __init__(self, docs_dir: Path, pages: Sequence[PurePosixPath]) -> None:
        self.docs_dir = docs_dir
        self.entries: dict[PurePosixPath, _Entry] = {}
        self.unvisited: dict[PurePosixPath, _Entry] = {}
        self._titles: dict[PurePosixPath, str | None] = {}
        for path in pages:
            for parent in reversed(path.parents):
                if parent != PurePosixPath(".") and parent not in self.entries:
                    self._add(_Entry(parent, docs_dir / parent, is_dir=True))
            self._add(_Entry(path, docs_dir / path, is_dir=False))

    def _add(self, entry: _Entry) -> None:
        self.entries[entry.path] = entry
        self.unvisited[entry.path] = entry

    def get(self, path: PurePosixPath) -> _Entry | None:
        return self.entries.get(path)

    def visit(self, entry: _Entry) -> None:
        self.unvisited.pop(entry.path, None)

    def declared_title(self, entry: _Entry) -> str | None:
        """The ``title`` of a page's front matter, read once per page."""
        if entry.path not in self._titles:
            metadata, _ = split_front_matter(_read_text(entry.abs_path))
            declared = metadata.get("title")
            self._titles[entry.path] = declared if isinstance(declared, str) else None
        return self._titles[entry.path]


@dataclass(slots=True)
class _PageNode:
    """A page listed in, or matched by, a navigation."""

    entry: _Entry
    title: str | None = None

    @property
    def path(self) -> PurePosixPath:
        return self.entry.path

    def resolve(self, context: _Context) -> _PageNode:
        context.visit(self.entry)
        return self


@dataclass(slots=True)
class _LinkNode:
    """An external link listed in a navigation."""

    title: str
    url: str


@dataclass(slots=True)
class _SectionNode:
    """A section: a directory, or an inline ``Title: [items]`` group."""

    title: str
    path: PurePosixPath
    children: list[Any]


def _inherited(data: dict[str, Any], option: str, parent: _NavConfig | None) -> bool:
    """A boolean option: the directory's own value, else the parent's, else off."""
    value = data.get(option)
    if isinstance(value, bool):
        return value
    return bool(getattr(parent, option)) if parent is not None else False


class _NavConfig:
    """A ``.nav.yml``, with the options a parent directory passes down."""

    def __init__(
        self,
        data: dict[str, Any],
        *,
        docs_dir: Path,
        directory: PurePosixPath,
        source: PurePosixPath | None = None,
        parent: _NavConfig | None = None,
    ) -> None:
        self.docs_dir = docs_dir
        self.directory = directory
        self.source = source
        title = data.get("title")
        self.title = title if isinstance(title, str) and title else None
        self.hide = bool(data.get("hide", False))
        self.preserve_directory_names = _inherited(data, "preserve_directory_names", parent)
        self.flatten_single_child_sections = _inherited(
            data, "flatten_single_child_sections", parent
        )
        self.use_index_title = _inherited(data, "use_index_title", parent)
        self.append_unmatched = _inherited(data, "append_unmatched", parent)
        self.sort = self._resolve_sort(data.get("sort"), parent)
        self.ignore = self._resolve_ignore(data.get("ignore"), parent)
        self.items = self._resolve_items(data.get("nav"))

    @staticmethod
    def load(docs_dir: Path, directory: PurePosixPath, parent: _NavConfig | None) -> _NavConfig:
        """Read ``directory``'s ``.nav.yml``, or fall back to the inherited defaults."""
        source = directory / NAV_CONFIG_FILENAME
        path = docs_dir / source
        if path.is_file():
            try:
                data = yaml.safe_load(_read_text(path))
            except yaml.YAMLError:
                logger.warning("Cannot parse %s", source)
                data = None
            if not isinstance(data, dict):
                data = {}
            return _NavConfig(
                data, docs_dir=docs_dir, directory=directory, source=source, parent=parent
            )
        return _NavConfig({}, docs_dir=docs_dir, directory=directory, parent=parent)

    def _resolve_sort(self, data: Any, parent: _NavConfig | None) -> _SortConfig:
        inherited = parent.sort if parent is not None else _SortConfig()
        if not isinstance(data, dict):
            return inherited
        return _SortConfig(
            by=data.get("by") or inherited.by,
            direction=data.get("direction") or inherited.direction,
            type=data.get("type") or inherited.type,
            sections=data.get("sections") or inherited.sections,
            ignore_case=bool(data.get("ignore_case") or inherited.ignore_case),
        )

    def _resolve_ignore(self, data: Any, parent: _NavConfig | None) -> tuple[_Glob, ...]:
        if data is None:
            return parent.ignore if parent is not None else ()
        patterns = [data] if isinstance(data, str) else list(data)
        globs: list[_Glob] = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                continue
            if pattern == "$inherit":
                if parent is not None:
                    globs.extend(parent.ignore)
                continue
            base = self.directory if pattern.startswith("/") else self.directory / "**"
            globs.append(_compile_glob(_absolute_pattern(base, pattern.removeprefix("/"))))
        return tuple(globs)

    def _resolve_items(self, data: Any) -> tuple[_ConfigItem, ...]:
        if isinstance(data, list):
            items = [_parse_config_item(entry) for entry in data]
            parsed = [item for item in items if item is not None]
        else:
            parsed = [_PatternItem(glob, ignore_no_matches=True) for glob in _DEFAULT_NAV_GLOBS]
        if self.append_unmatched:
            parsed.append(_PatternItem("*", ignore_no_matches=True))
        return tuple(parsed)


@dataclass(frozen=True, slots=True)
class _PathItem:
    """A ``path``, ``Title: path`` or ``Title: https://…`` nav entry."""

    value: str
    title: str | None = None

    def build(self, config: _NavConfig, context: _Context) -> Any:
        entry = context.get(PurePosixPath(config.directory / self.value))
        if entry is not None and not entry.is_dir:
            return _PageNode(entry, self.title)
        if entry is not None:
            return _DirNode(entry, parent_config=config, title=self.title)
        if self.title is not None:
            return _LinkNode(self.title, self.value)
        return _PatternNode(self.value, config)


@dataclass(frozen=True, slots=True)
class _InlineSectionItem:
    """A ``Title: [items]`` nav entry."""

    title: str
    children: tuple[_ConfigItem, ...]

    def build(self, config: _NavConfig, context: _Context) -> _SectionNode:
        children = [child.build(config, context) for child in self.children]
        return _SectionNode(self.title, config.directory, children)


@dataclass(frozen=True, slots=True)
class _PatternItem:
    """A glob nav entry, with the options that apply to what it matches."""

    glob: str
    options: tuple[tuple[str, Any], ...] = ()
    ignore_no_matches: bool = False

    def build(self, config: _NavConfig, context: _Context) -> _PatternNode:
        local = _NavConfig(
            dict(self.options),
            docs_dir=config.docs_dir,
            directory=config.directory,
            source=config.source,
            parent=config,
        )
        return _PatternNode(self.glob, local, ignore_no_matches=self.ignore_no_matches)


_ConfigItem = _PathItem | _InlineSectionItem | _PatternItem

_PATTERN_OPTIONS = frozenset(
    {
        "glob",
        "flatten_single_child_sections",
        "preserve_directory_names",
        "sort",
        "ignore",
        "append_unmatched",
        "ignore_no_matches",
    }
)


def _parse_config_item(entry: Any) -> _ConfigItem | None:
    """Turn one ``nav:`` entry into the item ``mkdocs-awesome-nav`` would build."""
    if isinstance(entry, str):
        return _PathItem(entry) if entry else None
    if not isinstance(entry, dict) or not entry:
        return None
    if len(entry) == 1:
        # A one-key mapping is always a title and a target, even when the key
        # happens to be "glob": the plugin's own union resolves it that way,
        # so a pattern with options is written as a mapping of several keys.
        (key, value) = next(iter(entry.items()))
        if isinstance(value, str):
            return _PathItem(value, str(key))
        if isinstance(value, list):
            children = [_parse_config_item(child) for child in value]
            return _InlineSectionItem(str(key), tuple(c for c in children if c is not None))
        return None
    glob = entry.get("glob")
    if isinstance(glob, str) and set(entry) <= _PATTERN_OPTIONS:
        options = tuple(
            (key, value) for key, value in entry.items() if key not in ("glob", "ignore_no_matches")
        )
        return _PatternItem(glob, options, bool(entry.get("ignore_no_matches", False)))
    return None


@dataclass(slots=True)
class _DirNode:
    """A directory of the documentation tree, resolved into a section."""

    entry: _Entry
    parent_config: _NavConfig
    title: str | None = None
    config: _NavConfig = field(init=False)

    def __post_init__(self) -> None:
        self.config = _NavConfig.load(
            self.parent_config.docs_dir, self.entry.path, self.parent_config
        )
        self.title = self.title or self.config.title

    @property
    def path(self) -> PurePosixPath:
        return self.entry.path

    def resolve(self, context: _Context) -> Any:
        context.visit(self.entry)
        title = self.title or self._generate_title(context)
        children = _resolve_nodes(self._build_children(context), context)
        if not children:
            return []
        if self.config.flatten_single_child_sections and len(children) == 1:
            child = children[0]
            if isinstance(child, (_PageNode, _SectionNode)):
                return child
        return _SectionNode(title, self.path, children)

    def _build_children(self, context: _Context) -> list[Any]:
        return [item.build(self.config, context) for item in self.config.items]

    def _generate_title(self, context: _Context) -> str:
        if self.config.preserve_directory_names:
            return self.path.name
        if self.config.use_index_title:
            index = context.get(self.path / "index.md")
            if index is not None:
                declared = context.declared_title(index)
                if declared:
                    return declared
        return _dirname_to_title(self.path.name)


@dataclass(slots=True)
class _PatternNode:
    """A glob nav entry, resolved into the pages and sections it claims."""

    pattern: str
    config: _NavConfig
    ignore_no_matches: bool = False

    def resolve(self, context: _Context) -> list[Any]:
        glob = _compile_glob(_absolute_pattern(self.config.directory, self.pattern))
        matches: list[Any] = []
        for entry in list(context.unvisited.values()):
            subject = entry.subject
            if not glob.match(subject):
                continue
            if any(ignored.match(subject) for ignored in self.config.ignore):
                continue
            if entry.is_dir:
                node = _DirNode(entry, parent_config=self.config)
                if not node.config.hide:
                    matches.append(node)
            else:
                matches.append(_PageNode(entry))
        if not matches and not self.ignore_no_matches:
            logger.warning(
                "The nav item '%s' doesn't match any files or directories (%s)",
                self.pattern,
                self.config.source or "<defaults>",
            )
        items = _resolve_nodes(matches, context)
        _sort_nodes(items, self.config.sort, context)
        return items


def _resolve_nodes(nodes: list[Any], context: _Context) -> list[Any]:
    """Resolve pages, then directories deepest first, then patterns."""
    for _, holder, index, node in sorted(_resolve_queue(nodes), key=lambda item: item[0]):
        holder[index] = node.resolve(context)
    return _flatten(nodes)


def _resolve_queue(nodes: list[Any]) -> Iterator[tuple[tuple[int, ...], list[Any], int, Any]]:
    for index, node in enumerate(nodes):
        if isinstance(node, _SectionNode):
            yield from _resolve_queue(node.children)
        elif isinstance(node, _PageNode):
            yield (1, index), nodes, index, node
        elif isinstance(node, _DirNode):
            yield (2, -len(node.path.parts), index), nodes, index, node
        elif isinstance(node, _PatternNode):
            yield (3, index), nodes, index, node


def _flatten(nodes: list[Any]) -> list[Any]:
    flat: list[Any] = []
    for node in nodes:
        if isinstance(node, list):
            flat.extend(node)
        else:
            flat.append(node)
    for node in flat:
        if isinstance(node, _SectionNode):
            node.children = _flatten(node.children)
    return flat


def _sort_nodes(nodes: list[Any], sort: _SortConfig, context: _Context) -> None:
    """Order a pattern's matches, keeping sections apart unless they are mixed."""

    def key(node: Any) -> Any:
        return _sort_key(_node_sort_value(node, sort, context), sort)

    nodes.sort(key=key, reverse=sort.direction == "desc")
    if sort.sections != "mixed":
        nodes.sort(
            key=lambda node: 2 if isinstance(node, _SectionNode) else 1,
            reverse=sort.sections == "first",
        )


def _node_sort_value(node: Any, sort: _SortConfig, context: _Context) -> str | tuple[str, ...]:
    path = node.path
    if sort.by == "filename":
        return (path.name, path.as_posix())
    if sort.by == "title":
        if isinstance(node, _SectionNode):
            return (node.title, path.name, path.as_posix())
        title = context.declared_title(node.entry) or path.name
        return (title, path.name, path.as_posix())
    return path.as_posix()


def _resolve_awesome_nav(docs_dir: Path, pages: Sequence[PurePosixPath]) -> tuple[NavItem, ...]:
    context = _Context(docs_dir, pages)
    root = _NavConfig.load(docs_dir, PurePosixPath("."), parent=None)
    nodes = [item.build(root, context) for item in root.items]
    return _to_navigation(_resolve_nodes(nodes, context))


def _to_navigation(nodes: Sequence[Any]) -> tuple[NavItem, ...]:
    items: list[NavItem] = []
    for node in nodes:
        if isinstance(node, _PageNode):
            items.append(NavPage(node.title, node.path.as_posix(), node.entry.abs_path))
        elif isinstance(node, _LinkNode):
            items.append(NavLink(node.title, node.url))
        elif isinstance(node, _SectionNode):
            items.append(_make_section(node.title, _to_navigation(node.children)))
    return tuple(items)


def _make_section(title: str, children: Sequence[NavItem]) -> NavSection:
    """Build a section, promoting a leading ``index.md`` to the section's own page."""
    index: NavPage | None = None
    if children and isinstance(children[0], NavPage):
        first = children[0]
        stem = PurePosixPath(first.src_uri).stem
        if stem in INDEX_STEMS:
            index = first
            children = children[1:]
    return NavSection(title, tuple(children), index)


# A plain MkDocs nav, and MkDocs' default when there is none


def _resolve_mkdocs_nav(
    nav: Sequence[Any], docs_dir: Path, pages: Sequence[PurePosixPath]
) -> tuple[NavItem, ...]:
    known = {path.as_posix() for path in pages}
    items: list[NavItem] = []
    for entry in nav:
        item = _mkdocs_nav_item(entry, docs_dir, known)
        if item is not None:
            items.append(item)
    return tuple(items)


def _mkdocs_nav_item(entry: Any, docs_dir: Path, known: set[str]) -> NavItem | None:
    if isinstance(entry, str):
        return _mkdocs_nav_target(None, entry, docs_dir, known)
    if not isinstance(entry, dict) or len(entry) != 1:
        return None
    (key, value) = next(iter(entry.items()))
    if isinstance(value, str):
        return _mkdocs_nav_target(str(key), value, docs_dir, known)
    if isinstance(value, list):
        children = [_mkdocs_nav_item(child, docs_dir, known) for child in value]
        return _make_section(str(key), [child for child in children if child is not None])
    return None


def _mkdocs_nav_target(title: str | None, path: str, docs_dir: Path, known: set[str]) -> NavItem:
    src_uri = PurePosixPath(path.lstrip("/")).as_posix()
    if src_uri in known:
        return NavPage(title, src_uri, docs_dir / src_uri)
    return NavLink(title or path, path)


def _default_nav(docs_dir: Path, pages: Sequence[PurePosixPath]) -> tuple[NavItem, ...]:
    """Nest every page by directory, the way MkDocs does without a ``nav``."""
    root: list[Any] = []
    sections: dict[PurePosixPath, list[Any]] = {PurePosixPath("."): root}
    for path in sorted(pages, key=_page_sort_key):
        branch = root
        directory = PurePosixPath(".")
        for part in path.parent.parts:
            directory = directory / part
            if directory not in sections:
                children: list[Any] = []
                sections[directory] = children
                branch.append((_dirname_to_title(part), children))
            branch = sections[directory]
        branch.append(NavPage(None, path.as_posix(), docs_dir / path))
    return _nested_to_navigation(root)


def _nested_to_navigation(branch: Sequence[Any]) -> tuple[NavItem, ...]:
    items: list[NavItem] = []
    for node in branch:
        if isinstance(node, tuple):
            title, children = node
            items.append(_make_section(title, _nested_to_navigation(children)))
        else:
            items.append(node)
    return tuple(items)


def _page_sort_key(path: PurePosixPath) -> tuple[tuple[str, ...], bool, str]:
    """MkDocs' ``file_sort_key``: by directory, index first, then filename."""
    parts = path.parts
    return (parts[:-1], PurePosixPath(parts[-1]).stem not in INDEX_STEMS, parts[-1])
