"""Read a site generator's configuration file without running the generator.

MkDocs keeps its settings in ``mkdocs.yml``, Zensical in ``zensical.toml``
under a ``[project]`` table; the keys TeXSmith cares about are the same in
both: where the sources are, where the site goes, the site language, the
navigation, the ``texsmith`` plugin options and the ``pymdownx.snippets``
base path. :func:`load_site_config` reads either into one
:class:`SiteConfig`, so the Zensical extension and ``texsmith site build``
can learn what MkDocs learns from its own loader.

Reading ``mkdocs.yml`` means meeting the tags MkDocs puts in it. They are
honoured here without importing anything: ``!ENV`` looks an environment
variable up, ``!relative`` resolves ``$config_dir``/``$docs_dir`` to real
directories, and ``!!python/name:...`` keeps its dotted name as a plain
string — a configuration file is data, and reading it never executes code.
``INHERIT:`` pulls a parent file in and the child wins, as MkDocs does it.

The MkDocs plugin does not come through here: at build time the live
``MkDocsConfig`` is the generator's truth. What both paths share are the
pure functions below — :func:`language_from_mapping`,
:func:`snippet_base_paths_from_extensions`,
:func:`snippet_auto_append_from_extensions`, :func:`site_declarations`,
:func:`web_options` and :func:`web_tags` — which read a theme mapping, an
extension list and the ``texsmith`` options whatever produced them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Any

import yaml


try:  # pragma: no cover - Python 3.11+
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


__all__ = [
    "CONFIG_NAMES",
    "WEB_TAGS_CHOICES",
    "WEB_TAGS_DEFAULT",
    "WEB_TYPOGRAPHY_CHOICES",
    "SiteConfig",
    "config_file_in",
    "language_from_mapping",
    "load_site_config",
    "option",
    "plugin_options",
    "site_declarations",
    "snippet_auto_append_from_extensions",
    "snippet_base_paths_from_extensions",
    "web_options",
    "web_tags",
    "web_typography",
]

_log = logging.getLogger("texsmith.site")

#: The ``markdown_extensions`` entry whose ``base_path`` the deprecated
#: ``--8<--`` include resolves against.
SNIPPETS_EXTENSION = "pymdownx.snippets"

#: The configuration files a site generator reads, most specific first.
CONFIG_NAMES = ("mkdocs.yml", "mkdocs.yaml", "zensical.toml")

#: What ``web.tags`` accepts: derive a page's tags from its index entries,
#: or derive none and leave the page's own ``tags:`` as it is.
WEB_TAGS_CHOICES = frozenset({"index", "none"})

#: A site with index entries browses by them unless it says otherwise.
WEB_TAGS_DEFAULT = "index"

#: What ``web.typography`` accepts: the French rules, or none at all. There
#: is no default value — the option's absence means the site's language
#: decides (:func:`web_typography`).
WEB_TYPOGRAPHY_CHOICES = frozenset({"fr", "none"})


def config_file_in(project_dir: Path) -> Path | None:
    """The configuration file of a project directory, ``None`` when there is none.

    One lookup for the Zensical extension, which has to find the options
    Zensical dropped from its own view of the file, and for ``texsmith site
    assets`` called without a path: both read the same file.
    """
    for name in CONFIG_NAMES:
        candidate = Path(project_dir) / name
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class SiteConfig:
    """What a site generator's configuration file says about a TeXSmith site."""

    #: The configuration file itself (``mkdocs.yml`` or ``zensical.toml``).
    config_path: Path
    #: Its directory: every relative path in the file resolves against it.
    project_dir: Path
    #: The Markdown sources (absolute; ``docs`` when the file is silent).
    docs_dir: Path
    #: Where the generator writes the site (absolute; ``site`` by default).
    site_dir: Path
    site_name: str | None
    #: ``theme.language``, then ``theme.locale``, then ``site_language``.
    language: str | None
    #: The raw ``nav:`` value, untouched.
    nav: list[Any] | None
    #: The options of the ``texsmith`` plugin (``{}`` when it is not listed).
    plugin: dict[str, Any]
    #: ``pymdownx.snippets``' ``base_path``, resolved against ``project_dir``.
    snippet_base_paths: list[Path]
    #: ``pymdownx.snippets``' ``auto_append``, resolved along ``base_path``:
    #: the files the extension appends to every page of the site.
    snippet_auto_append: list[Path]
    #: The raw ``exclude_docs`` block: gitignore-style patterns, one per line.
    exclude_docs: str | None
    #: The whole parsed mapping. For ``zensical.toml`` the site keys live one
    #: level down, under ``raw["project"]``.
    raw: Mapping[str, Any]
    #: Whether a page is served from its own directory (``guide/mkdocs/``)
    #: rather than from a file next to it (``guide/mkdocs.html``).
    use_directory_urls: bool = True

    @property
    def data(self) -> Mapping[str, Any]:
        """The site-level mapping: ``raw``, or its ``[project]`` table for Zensical."""
        project = self.raw.get("project")
        return project if isinstance(project, Mapping) else self.raw


def option(source: Any, key: str) -> Any:
    """``source[key]`` whether ``source`` is a mapping or a settings object."""
    if source is None:
        return None
    getter = getattr(source, "get", None)
    if callable(getter):
        try:
            return getter(key)
        except (KeyError, TypeError):  # pragma: no cover - exotic mapping
            return None
    return getattr(source, key, None)


def language_from_mapping(theme: Any, site_language: Any = None) -> str | None:
    """The site's language: ``theme.language``, ``theme.locale``, ``site_language``.

    ``theme`` is a mapping in a configuration file and a ``Theme`` object in a
    running MkDocs build; both answer ``get``. A ``locale`` is a language tag
    in the file and a ``Locale`` object at runtime, so its ``language``
    attribute comes first and its string form is the fallback.
    """
    language = option(theme, "language")
    if language:
        return str(language)
    locale = option(theme, "locale")
    if locale is not None:
        tag = getattr(locale, "language", None) or str(locale)
        if tag:
            return str(tag)
    if site_language:
        return str(site_language)
    return None


def _extension_options(markdown_extensions: Any, name: str) -> Mapping[str, Any] | None:
    """The options of one Markdown extension, from either spelling.

    A configuration file writes ``markdown_extensions`` as a list whose
    entries are a name or a one-key mapping; MkDocs hands the same thing out
    at runtime as ``mdx_configs``, a mapping keyed by extension name.
    """
    if isinstance(markdown_extensions, Mapping):
        options = markdown_extensions.get(name)
        return options if isinstance(options, Mapping) else None
    if isinstance(markdown_extensions, Sequence) and not isinstance(
        markdown_extensions, str | bytes
    ):
        for entry in markdown_extensions:
            if isinstance(entry, Mapping):
                options = entry.get(name)
                if isinstance(options, Mapping):
                    return options
    return None


def _extension_declared(markdown_extensions: Any, name: str) -> bool:
    """Whether the site enables one Markdown extension, with or without options."""
    if _extension_options(markdown_extensions, name) is not None:
        return True
    if isinstance(markdown_extensions, Mapping):
        return name in markdown_extensions
    if isinstance(markdown_extensions, Sequence) and not isinstance(
        markdown_extensions, str | bytes
    ):
        return any(
            entry == name or (isinstance(entry, Mapping) and name in entry)
            for entry in markdown_extensions
        )
    return False


def snippet_base_paths_from_extensions(markdown_extensions: Any, project_dir: Path) -> list[Path]:
    """The ``base_path`` of the site's ``pymdownx.snippets``, as directories.

    The deprecated ``--8<-- "path"`` include resolves against that base path,
    not against the page, so the PDF export has to search it too. The value
    may be one path or a list, and a ``!relative`` tag arrives as a
    placeholder object that spells itself out through :func:`os.fspath`
    (``!relative $config_dir`` is the directory of the configuration file).

    A site that enables the extension without naming a ``base_path`` gets the
    project directory, which is what ``pymdownx.snippets`` itself uses: its
    default is ``['.']``, relative to the working directory a build runs from.
    Only a site that does not enable the extension at all gets no search path.
    """
    if not _extension_declared(markdown_extensions, SNIPPETS_EXTENSION):
        return []
    section = _extension_options(markdown_extensions, SNIPPETS_EXTENSION)
    raw = section.get("base_path") if section is not None else None
    if raw is None:
        return [Path(os.path.normpath(project_dir))]
    candidates = raw if isinstance(raw, list | tuple) else [raw]
    paths: list[Path] = []
    for candidate in candidates:
        try:
            path = Path(os.fspath(candidate))
        except TypeError:
            _log.warning(
                "Ignoring 'pymdownx.snippets.base_path' entry %r: not a path.",
                candidate,
            )
            continue
        if not path.is_absolute():
            path = project_dir / path
        resolved = Path(os.path.normpath(path))
        if resolved not in paths:
            paths.append(resolved)
    return paths


def snippet_auto_append_from_extensions(
    markdown_extensions: Any, base_paths: Sequence[Path]
) -> list[Path]:
    """The files ``pymdownx.snippets`` appends to every page, as real files.

    ``auto_append`` is how a site gives every page a shared block without
    writing it anywhere — the abbreviation list is what it is for — so the
    book builder has to append the same thing or the acronyms of a whole site
    reach no PDF. Each entry is resolved along ``base_path``, as the
    extension resolves it; an entry no base path holds is dropped with a
    warning, since a missing file is a site configuration error, not a page's.
    """
    section = _extension_options(markdown_extensions, SNIPPETS_EXTENSION)
    raw = section.get("auto_append") if section is not None else None
    if raw is None:
        return []
    candidates = raw if isinstance(raw, list | tuple) else [raw]
    files: list[Path] = []
    for candidate in candidates:
        try:
            entry = Path(os.fspath(candidate))
        except TypeError:
            _log.warning(
                "Ignoring 'pymdownx.snippets.auto_append' entry %r: not a path.",
                candidate,
            )
            continue
        found = _first_existing(entry, base_paths)
        if found is None:
            _log.warning(
                "texsmith: 'pymdownx.snippets.auto_append' names '%s', which no "
                "'base_path' holds; the books will not carry it.",
                entry,
            )
            continue
        if found not in files:
            files.append(found)
    return files


def _first_existing(entry: Path, base_paths: Sequence[Path]) -> Path | None:
    """``entry`` itself when absolute, else the first base path that holds it."""
    if entry.is_absolute():
        return entry if entry.is_file() else None
    for base in base_paths:
        candidate = Path(os.path.normpath(base / entry))
        if candidate.is_file():
            return candidate
    return None


def plugin_options(plugins: Any, name: str) -> dict[str, Any]:
    """The options of one plugin, ``{}`` when it is listed bare or absent.

    ``plugins:`` is a list whose entries are either a plugin name or a
    one-key mapping from the name to its options; MkDocs also accepts the
    whole thing written as a mapping.
    """
    if isinstance(plugins, Mapping):
        options = plugins.get(name)
        return dict(options) if isinstance(options, Mapping) else {}
    if isinstance(plugins, Sequence) and not isinstance(plugins, str | bytes):
        for entry in plugins:
            if isinstance(entry, str):
                continue
            if isinstance(entry, Mapping):
                options = entry.get(name)
                if options is not None:
                    return dict(options) if isinstance(options, Mapping) else {}
    return {}


def site_declarations(
    options: Mapping[str, Any], *, logger: logging.Logger | None = None
) -> dict[str, Any]:
    """The site-wide ``declare`` of the ``texsmith`` plugin options, kind by kind.

    ``options`` is the plugin's option mapping — MkDocs' validated
    ``self.config`` or the ``texsmith:`` block of the configuration file. The
    kinds are the front matter's own (``counters``, ``admonitions``,
    ``glossary``…): they are merged under each page's ``press.declare`` and
    handed to the parser, so nothing here knows one from another.
    """
    log = logger or _log
    declare = options.get("declare") or {}
    if not isinstance(declare, Mapping):
        log.warning(
            "texsmith: 'declare' must map a kind to its declarations; ignoring %r.",
            type(declare).__name__,
        )
        return {}
    declared: dict[str, Any] = {}
    for kind, value in declare.items():
        if not isinstance(value, Mapping):
            log.warning(
                "texsmith: 'declare.%s' must map a name to its declaration; ignoring %r.",
                kind,
                type(value).__name__,
            )
            continue
        declared[str(kind)] = dict(value)
    return declared


def web_options(
    options: Mapping[str, Any], *, logger: logging.Logger | None = None
) -> dict[str, Any]:
    """The ``web:`` options ``tmark.lower_web`` accepts, from the plugin options."""
    log = logger or _log
    raw = options.get("web") or {}
    resolved: dict[str, Any] = {}
    if not isinstance(raw, Mapping):
        log.warning("texsmith: 'web' must be a mapping; ignoring %r.", type(raw).__name__)
        return resolved
    for key in ("sections", "citations", "css_prefix"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            resolved[key] = value.strip()
    return resolved


def web_tags(options: Mapping[str, Any], *, logger: logging.Logger | None = None) -> str:
    """``web.tags``: which index entries of a page become tags of the page.

    ``index`` (the default) turns every entry's top level into a tag, and
    ``none`` leaves the page's own ``tags:`` alone. This is TeXSmith's own
    option, not one :func:`web_options` hands to ``tmark.lower_web``: the
    terms reach the generator as page metadata, never as a lowering setting.
    """
    log = logger or _log
    raw = options.get("web") or {}
    if not isinstance(raw, Mapping):
        return WEB_TAGS_DEFAULT
    value = raw.get("tags")
    if value is None:
        return WEB_TAGS_DEFAULT
    if isinstance(value, str) and value.strip() in WEB_TAGS_CHOICES:
        return value.strip()
    log.warning(
        "texsmith: 'web.tags' must be one of %s; ignoring %r and keeping '%s'.",
        ", ".join(sorted(WEB_TAGS_CHOICES)),
        value,
        WEB_TAGS_DEFAULT,
    )
    return WEB_TAGS_DEFAULT


def web_typography(
    options: Mapping[str, Any],
    *,
    lang: str | None = None,
    logger: logging.Logger | None = None,
) -> str | None:
    """``web.typography``: the typographic rules a rendered page goes through.

    ``fr`` spaces the punctuation the French way and turns the straight
    quotes into guillemets, ``none`` leaves the HTML as Python-Markdown
    wrote it. Unset — the usual case — the site's language decides: a
    document declared ``fr`` on the web gets what ``babel-french`` already
    gives it in the PDF, and every other language gets nothing. ``None`` is
    the answer for "no rules", so a caller has one thing to test.

    This is TeXSmith's own option, like ``web.tags``: the rules run over the
    rendered HTML, long after ``tmark.lower_web`` has had its say, so
    :func:`web_options` does not carry it.
    """
    log = logger or _log
    raw = options.get("web") or {}
    value = raw.get("typography") if isinstance(raw, Mapping) else None
    if value is None:
        return "fr" if (lang or "").lower().partition("-")[0] == "fr" else None
    if isinstance(value, str) and value.strip() in WEB_TYPOGRAPHY_CHOICES:
        choice = value.strip()
        return None if choice == "none" else choice
    log.warning(
        "texsmith: 'web.typography' must be one of %s; ignoring %r and keeping "
        "what the site language says.",
        ", ".join(sorted(WEB_TYPOGRAPHY_CHOICES)),
        value,
    )
    return web_typography({}, lang=lang, logger=log)


@dataclass(frozen=True, slots=True)
class _Relative:
    """An unresolved ``!relative`` tag: the spec as the file spelled it."""

    spec: str


def _env_value(node_value: Any) -> Any:
    """``!ENV NAME`` or ``!ENV [NAME, ..., default]``, the MkDocs way."""
    if isinstance(node_value, list):
        if not node_value:
            return None
        *names, default = node_value
        if not names:  # a one-item list names a variable with no default
            return os.environ.get(str(default))
        for name in names:
            value = os.environ.get(str(name))
            if value is not None:
                return value
        return default
    return os.environ.get(str(node_value))


def _config_loader() -> type[yaml.SafeLoader]:
    """A ``SafeLoader`` that reads the MkDocs tags and imports nothing."""

    class ConfigLoader(yaml.SafeLoader):
        pass

    def construct_env(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
        if isinstance(node, yaml.SequenceNode):
            return _env_value(loader.construct_sequence(node, deep=True))
        return _env_value(loader.construct_scalar(node))  # type: ignore[arg-type]

    def construct_relative(loader: yaml.SafeLoader, node: yaml.Node) -> _Relative:
        if isinstance(node, yaml.ScalarNode):
            return _Relative(str(loader.construct_scalar(node) or ""))
        return _Relative("")

    def construct_python_name(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> str:
        """``!!python/name:a.b.c`` keeps its dotted name; it never imports."""
        del loader, node
        return suffix

    ConfigLoader.add_constructor("!ENV", construct_env)
    ConfigLoader.add_constructor("!relative", construct_relative)
    ConfigLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", construct_python_name)
    return ConfigLoader


def _merge(parent: Mapping[str, Any], child: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-merge ``child`` over ``parent``; a mapping recurses, anything wins."""
    merged = dict(parent)
    for key, value in child.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = _merge(current, value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path, *, seen: frozenset[Path] = frozenset()) -> dict[str, Any]:
    """One ``mkdocs.yml``, its ``INHERIT`` parent merged under it."""
    resolved = path.resolve()
    if resolved in seen:
        raise ValueError(f"'INHERIT' loops back to {path}")
    data = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=_config_loader())
    if data is None:
        data = {}
    if not isinstance(data, dict):
        # A configuration file that is not a mapping is a bad file, not a
        # caller passing the wrong type: ValueError, as the loader above.
        raise ValueError(f"{path} does not hold a mapping")  # noqa: TRY004
    inherit = data.pop("INHERIT", None)
    if inherit is None:
        return data
    parent_path = Path(os.fspath(inherit))
    if not parent_path.is_absolute():
        parent_path = path.parent / parent_path
    parent = _read_yaml(parent_path, seen=seen | {resolved})
    return _merge(parent, data)


def _resolve_relatives(value: Any, project_dir: Path, docs_dir: Path) -> Any:
    """Replace every ``!relative`` placeholder by the directory it names."""
    if isinstance(value, _Relative):
        spec = value.spec.strip()
        if not spec:
            return project_dir
        head, _, tail = spec.partition("/")
        base = {"$config_dir": project_dir, "$docs_dir": docs_dir}.get(head)
        if base is None:
            candidate = Path(spec)
            return candidate if candidate.is_absolute() else project_dir / candidate
        return base / tail if tail else base
    if isinstance(value, Mapping):
        return {key: _resolve_relatives(item, project_dir, docs_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_relatives(item, project_dir, docs_dir) for item in value]
    return value


def _directory(data: Mapping[str, Any], key: str, default: str, base: Path) -> Path:
    raw = data.get(key)
    path = Path(os.fspath(raw)) if raw is not None else Path(default)
    if not path.is_absolute():
        path = base / path
    return Path(os.path.normpath(path))


def load_site_config(path: Path) -> SiteConfig:
    """Read ``mkdocs.yml`` or ``zensical.toml`` into a :class:`SiteConfig`."""
    config_path = Path(path)
    project_dir = config_path.parent.resolve()
    suffix = config_path.suffix.lower()
    if suffix == ".toml":
        raw: dict[str, Any] = tomllib.loads(config_path.read_text(encoding="utf-8"))
        project = raw.get("project")
        data: Mapping[str, Any] = project if isinstance(project, Mapping) else raw
    elif suffix in {".yml", ".yaml"}:
        raw = _read_yaml(config_path)
        docs_dir = _directory(raw, "docs_dir", "docs", project_dir)
        raw = _resolve_relatives(raw, project_dir, docs_dir)
        data = raw
    else:
        raise ValueError(f"Unsupported site configuration file: {config_path}")

    snippet_paths = snippet_base_paths_from_extensions(data.get("markdown_extensions"), project_dir)
    nav = data.get("nav")
    site_name = data.get("site_name")
    exclude_docs = data.get("exclude_docs")
    return SiteConfig(
        config_path=config_path,
        project_dir=project_dir,
        docs_dir=_directory(data, "docs_dir", "docs", project_dir),
        site_dir=_directory(data, "site_dir", "site", project_dir),
        site_name=str(site_name) if site_name is not None else None,
        language=language_from_mapping(data.get("theme"), data.get("site_language")),
        nav=list(nav) if isinstance(nav, list) else None,
        plugin=plugin_options(data.get("plugins"), "texsmith"),
        snippet_base_paths=snippet_paths,
        snippet_auto_append=snippet_auto_append_from_extensions(
            data.get("markdown_extensions"), snippet_paths
        ),
        exclude_docs=str(exclude_docs) if exclude_docs is not None else None,
        raw=raw,
        use_directory_urls=bool(data.get("use_directory_urls", True)),
    )
