"""Source files of a build and the byte-offset → line/column index.

``FileTable`` is the Python twin of tmark's ``FileId`` numbering: id 0 is the
main document, includes and loaded inventories take the following ids in the
order they are met. ``LineIndex`` follows ``tmark_ir::span::LineIndex`` so both
tools print identical positions (decision X10: 1-based line, 1-based **byte**
column).
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePath
import re
from typing import NewType


FileId = NewType("FileId", int)

_LINE_BREAK = re.compile(rb"\r\n|\r|\n")


@dataclass(frozen=True, slots=True)
class LineCol:
    """A printed position: 1-based line, 1-based byte column."""

    line: int
    col: int


class LineIndex:
    """Maps byte offsets of a UTF-8 text to lines and columns and back.

    Line endings are ``\\n``, ``\\r\\n`` and a lone ``\\r`` (CommonMark). Offsets
    past the end clamp to the end; an offset inside a multibyte character snaps
    to that character's start, so a column never points between two bytes of
    one glyph.
    """

    __slots__ = ("_data", "_ends", "_starts")

    def __init__(self, text: str) -> None:
        data = text.encode("utf-8")
        starts = [0]
        ends: list[int] = []
        for match in _LINE_BREAK.finditer(data):
            ends.append(match.start())
            starts.append(match.end())
        ends.append(len(data))
        self._data = data
        self._starts = starts
        self._ends = ends

    def __len__(self) -> int:
        """Total length in bytes."""
        return len(self._data)

    @property
    def line_count(self) -> int:
        """Number of lines, at least 1."""
        return len(self._starts)

    def line_start(self, line: int) -> int | None:
        """Byte offset where the 1-based ``line`` starts, ``None`` past the text."""
        index = line - 1
        if 0 <= index < len(self._starts):
            return self._starts[index]
        return None

    def line_end(self, line: int) -> int | None:
        """Byte offset of the terminator of the 1-based ``line`` (the end of the text for the last one)."""
        index = line - 1
        if 0 <= index < len(self._ends):
            return self._ends[index]
        return None

    def snap(self, offset: int) -> int:
        """Clamp ``offset`` to the text and move it back to a character boundary."""
        offset = max(0, min(offset, len(self._data)))
        while offset > 0 and offset < len(self._data) and (self._data[offset] & 0xC0) == 0x80:
            offset -= 1
        return offset

    def line_col(self, offset: int) -> LineCol:
        """The printed position of a byte offset."""
        offset = self.snap(offset)
        line = bisect_right(self._starts, offset) - 1
        return LineCol(line + 1, offset - self._starts[line] + 1)

    def offset(self, position: LineCol) -> int:
        """Byte offset of a printed position.

        A column past the end of the line clamps to the line's end, before its
        terminator; a line past the text clamps to the end of the text.
        """
        start = self.line_start(position.line)
        end = self.line_end(position.line)
        if start is None or end is None:
            return len(self._data)
        return min(start + max(position.col, 1) - 1, end)


@dataclass(slots=True)
class SourceFile:
    #: A concrete OS path for a real file, or a ``PurePosixPath`` for a caller
    #: (the mkdocs plugin) that already computed a posix-stable display name
    #: it wants printed unchanged (``str()`` of a native ``Path`` re-renders
    #: with the OS separator even when built from a posix-looking string).
    path: PurePath
    text: str
    _index: LineIndex | None = None

    @property
    def line_index(self) -> LineIndex:
        if self._index is None:
            self._index = LineIndex(self.text)
        return self._index


class FileTable:
    """The files of one build, addressed by :class:`FileId`.

    Paths are stored as given, without symlink resolution, so TeXSmith and
    tmark agree on the name a diagnostic prints. A file registered with an
    empty text (HTML input, a path only known by name) renders without a
    line and column.
    """

    __slots__ = ("_files",)

    def __init__(self) -> None:
        self._files: list[SourceFile] = []

    def add(self, path: PurePath | str, text: str) -> FileId:
        """Register a file and return its id (the next free one).

        A ``PurePath`` already given (a ``PurePosixPath`` display name, say)
        is kept as is; only a plain string is turned into a native ``Path``,
        as before. This is what lets a caller opt into a posix-stable name
        without changing what every other caller gets.
        """
        stored = path if isinstance(path, PurePath) else Path(path)
        self._files.append(SourceFile(stored, text))
        return FileId(len(self._files) - 1)

    def find(self, path: PurePath | str) -> FileId | None:
        """The id of the first file registered under ``path``, if any."""
        wanted = path if isinstance(path, PurePath) else Path(path)
        for index, entry in enumerate(self._files):
            if entry.path == wanted:
                return FileId(index)
        return None

    def get(self, file_id: int) -> SourceFile | None:
        if 0 <= file_id < len(self._files):
            return self._files[file_id]
        return None

    def path(self, file_id: int) -> PurePath:
        return self._entry(file_id).path

    def text(self, file_id: int) -> str:
        return self._entry(file_id).text

    def line_index(self, file_id: int) -> LineIndex:
        """The (lazily built, cached) index of a file."""
        return self._entry(file_id).line_index

    def _entry(self, file_id: int) -> SourceFile:
        entry = self.get(file_id)
        if entry is None:
            raise KeyError(f"no file with id {file_id}")
        return entry

    def __len__(self) -> int:
        return len(self._files)

    def __iter__(self) -> Iterator[FileId]:
        return (FileId(index) for index in range(len(self._files)))

    def __contains__(self, file_id: object) -> bool:
        return isinstance(file_id, int) and 0 <= file_id < len(self._files)


__all__ = ["FileId", "FileTable", "LineCol", "LineIndex", "SourceFile"]
