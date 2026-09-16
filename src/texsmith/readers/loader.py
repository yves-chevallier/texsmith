"""File loaders satisfying tmark's ``Loader`` protocol.

``tmark.resolve``, ``tmark.lint`` and ``tmark.write`` load includes,
bibliographies and cross-reference inventories through a loader:
``load(from_path, rel)`` returns the text of a file or ``None`` when there is
no such file (tmark then reports ``include-missing`` and friends at the right
span). :class:`TexsmithLoader` reads the file system and registers every file
it serves in the build's :class:`~texsmith.diagnostics.FileTable`, so a
diagnostic emitted in an included file prints that file's name;
:class:`MemoryLoader` serves a mapping for tests
(``specs/migration/python-ir-and-passes.md`` §7).

:class:`SearchPathLoader` wraps either one with the search path an include
falls back to — ``--include-path``, ``press.include_paths`` and the site's
``pymdownx.snippets`` base path — so the document's own directory decides
first and a path written against the base path is still found. Every include
of every backend goes through it: ``passes.include.resolve_include`` for the
conversion, and the ``loader`` ``texsmith.site.index`` hands
``tmark.lower_web`` for a fence's ``include=`` on the web.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path, PurePath
from typing import Protocol

from texsmith.diagnostics import NO_SPAN, DiagnosticSink, FileTable


__all__ = [
    "Loader",
    "MemoryLoader",
    "SearchPathLoader",
    "TexsmithLoader",
    "join",
    "join_dir",
]


class Loader(Protocol):
    """What tmark asks of a loader: the text of ``rel`` seen from ``from_path``."""

    def load(self, from_path: str, rel: str) -> str | None:
        """The file's text, or ``None`` when there is no such file."""
        ...


def join(from_path: str | PurePath, rel: str) -> str:
    """Resolve ``rel`` against ``from_path`` as ``tmark_registry::loader::join`` does.

    An absolute ``rel`` is returned as is. Otherwise it is joined to the
    directory of ``from_path`` — ``from_path`` itself when it has no extension
    (an ``{include base=…}`` directory) — and normalised textually: ``.``
    segments dropped, ``..`` folded into the previous segment when there is
    one. No symlink resolution, so TeXSmith and tmark print the same name.

    This is OS-native text (``PurePath`` is whatever flavour the running OS
    uses), because :class:`TexsmithLoader` and the disk-backed test fixtures
    key their file tables and caches by this same string to actually find a
    file on disk — forcing it to posix here previously broke every lookup
    keyed by a real ``str(Path(...))`` on Windows. A caller that needs a
    *display* name stable across OSes (a diagnostic, a label) normalises to
    posix at that boundary instead, once the real file has already been
    found (:meth:`texsmith.diagnostics.FileTable.add` and the mkdocs plugin's
    ``src_uri`` registration do exactly that).
    """
    origin = PurePath(from_path)
    return join_dir(origin.parent if origin.suffix else origin, rel)


def join_dir(directory: str | PurePath, rel: str) -> str:
    """Resolve ``rel`` against ``directory`` itself, never against its parent.

    :func:`join` reads its first argument as a file and tells a directory from
    it by the extension; the include search path
    (:attr:`~texsmith.passes.PassContext.include_paths`) already holds
    directories, and one whose last segment carries a dot would lose it.
    """
    target = PurePath(rel)
    if target.is_absolute():
        return str(target)
    base = PurePath(directory)
    parts: list[str] = []
    for part in (*base.parts, *target.parts):
        if part == ".":
            continue
        if part == "..":
            if parts and parts[-1] not in ("..", base.anchor):
                parts.pop()
            else:
                parts.append(part)
            continue
        parts.append(part)
    if not parts:
        return ""
    return str(PurePath(*parts))


class TexsmithLoader:
    """The file-system loader: reads UTF-8 text and records each file served.

    A missing file is ``None`` (tmark reports it); a file that exists but
    cannot be read or decoded is ``None`` too, with a ``file-unreadable``
    diagnostic in ``sink`` naming the path.
    """

    __slots__ = ("files", "served", "sink")

    def __init__(self, files: FileTable, sink: DiagnosticSink | None = None) -> None:
        self.files = files
        self.sink = sink
        #: ``path -> FileId`` of every file served, in order of first request.
        self.served: dict[str, int] = {}

    def load(self, from_path: str, rel: str) -> str | None:
        target = join(from_path, rel)
        try:
            text = Path(target).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as exc:
            if self.sink is not None:
                self.sink.emit("file-unreadable", NO_SPAN, f"'{target}': {exc}")
            return None
        if target not in self.served:
            known = self.files.find(target)
            self.served[target] = (
                int(known) if known is not None else int(self.files.add(target, text))
            )
        return text


class MemoryLoader:
    """A loader over an in-memory mapping ``{path: text}``; paths are joined like the file system's."""

    __slots__ = ("files", "requests")

    def __init__(self, files: Mapping[str, str] | None = None) -> None:
        self.files: dict[str, str] = dict(files or {})
        #: Every ``(from_path, rel)`` pair asked for, in order.
        self.requests: list[tuple[str, str]] = []

    def load(self, from_path: str, rel: str) -> str | None:
        self.requests.append((from_path, rel))
        target = join(from_path, rel)
        if target in self.files:
            return self.files[target]
        return self.files.get(rel)


class SearchPathLoader:
    """A loader that falls back to a search path when the relative lookup misses.

    The including file's directory decides first — the spec's §Includes rule,
    the only one ``{include}(file)`` ever needs. Only when that misses does
    the search path get a turn, in order: the deprecated ``--8<-- "path"``
    spelling and a fence's ``include=`` are written against the snippet base
    path of the site, not against the page.
    """

    __slots__ = ("base", "search")

    def __init__(self, base: Loader, search: Sequence[Path] = ()) -> None:
        self.base = base
        self.search = tuple(search)

    def locate(self, from_path: str, rel: str) -> tuple[str, str] | None:
        """``(path, text)`` of the file ``rel`` names, or ``None`` when nothing holds it.

        The path returned is the file actually read, so the file table and
        every diagnostic name a real one.
        """
        text = self.base.load(from_path, rel)
        if text is not None:
            return join(from_path, rel), text
        for directory in self.search:
            target = join_dir(directory, rel)
            # ``target`` is absolute: the loader's own join returns it as is.
            text = self.base.load(from_path, target)
            if text is not None:
                return target, text
        return None

    def load(self, from_path: str, rel: str) -> str | None:
        found = self.locate(from_path, rel)
        return None if found is None else found[1]
