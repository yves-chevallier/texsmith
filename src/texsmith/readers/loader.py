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
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePath, PurePosixPath

from texsmith.diagnostics import NO_SPAN, DiagnosticSink, FileTable


__all__ = ["MemoryLoader", "TexsmithLoader", "join", "join_dir"]


def _posix(value: str | PurePath) -> str:
    """Render an OS path or already-posix logical text as posix text.

    ``PurePath`` is whatever flavour the running OS uses, so this accepts a
    real filesystem path (native separators) as readily as a logical string
    already written with ``/`` — both parse the same way, since Windows
    accepts either separator. Rendering through :class:`PurePosixPath` keeps
    the *string form* stable across OSes even though the segments it counts
    (a drive letter, say) still reflect wherever the input came from.
    """
    return PurePath(value).as_posix()


def join(from_path: str | PurePath, rel: str) -> str:
    """Resolve ``rel`` against ``from_path`` as ``tmark_registry::loader::join`` does.

    An absolute ``rel`` is returned as is. Otherwise it is joined to the
    directory of ``from_path`` — ``from_path`` itself when it has no extension
    (an ``{include base=…}`` directory) — and normalised textually: ``.``
    segments dropped, ``..`` folded into the previous segment when there is
    one. No symlink resolution, so TeXSmith and tmark print the same name.

    The result is always posix-style text (forward slashes), never OS-native:
    it crosses into tmark and appears verbatim in diagnostics and labels, so
    it must read the same on every platform. Reading the file back from disk
    still goes through :class:`pathlib.Path`, which accepts forward slashes
    on every OS tmark and TeXSmith support.
    """
    origin = PurePosixPath(_posix(from_path))
    return join_dir(origin.parent if origin.suffix else origin, rel)


def join_dir(directory: str | PurePath, rel: str) -> str:
    """Resolve ``rel`` against ``directory`` itself, never against its parent.

    :func:`join` reads its first argument as a file and tells a directory from
    it by the extension; the include search path
    (:attr:`~texsmith.passes.PassContext.include_paths`) already holds
    directories, and one whose last segment carries a dot would lose it.
    """
    target = PurePosixPath(_posix(rel))
    if target.is_absolute():
        return str(target)
    base = PurePosixPath(_posix(directory))
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
    return str(PurePosixPath(*parts))


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
