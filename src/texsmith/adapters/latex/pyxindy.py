"""Helpers to integrate the PyXindy toolchain (Python port of xindy)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shlex
import shutil
import sys


_RESOURCE_DIR = Path(__file__).with_name("xindy")
_EMPTY_CLOSE_RE = re.compile(r'\s*:close\s+""')
_GLOSSARY_END_MARKERS = (
    "\\glsgroupskip",
    "\\glsgroupheading",
    "\\end{theglossary}",
)


def _python_module_available() -> bool:
    """Return True when the PyXindy modules are importable."""
    return importlib.util.find_spec("xindy") is not None


def is_available() -> bool:
    """Check whether PyXindy can be invoked (entry points or module)."""
    return _python_module_available() or shutil.which("makeindex-py") is not None


def _script_path(name: str) -> Path | None:
    """Resolve a script living alongside the current interpreter."""
    candidate = Path(sys.executable).with_name(name)
    return candidate if candidate.exists() else None


def index_command_tokens() -> list[str]:
    """Return the argv tokens to invoke the makeindex-compatible wrapper."""
    for candidate in ("makeindex-py", "makeindex4"):
        resolved = shutil.which(candidate) or _script_path(candidate)
        if resolved:
            return [str(resolved), "--input-encoding=utf-8", "--output-encoding=utf-8"]
    return [
        sys.executable,
        "-m",
        "xindy.tex.makeindex4",
        "--input-encoding=utf-8",
        "--output-encoding=utf-8",
    ]


def glossary_command_tokens() -> list[str]:
    """Return the argv tokens to invoke the makeglossaries helper."""
    for candidate in ("makeglossaries-py",):
        resolved = shutil.which(candidate) or _script_path(candidate)
        if resolved:
            return [str(resolved)]
    return [sys.executable, "-m", "xindy.tex.makeglossaries"]


def resource_dir() -> Path | None:
    """Return the bundled xindy resource directory when available."""
    return _RESOURCE_DIR if _RESOURCE_DIR.exists() else None


def sanitize_xdy(path: Path) -> bool:
    """Normalize glossaries-generated xdy files for the Python parser."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    updated = _EMPTY_CLOSE_RE.sub("", text)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def sanitize_glossary_output(path: Path) -> bool:
    """Fix PyXindy output so glossaries entries close correctly."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    has_trailing_newline = text.endswith("\n")
    updated = text.replace("~n", "\n")
    lines = updated.splitlines()
    out_lines: list[str] = []
    in_entry = False
    last_entry_idx: int | None = None
    for line in lines:
        stripped = line.strip()
        is_end = not stripped or stripped.startswith(_GLOSSARY_END_MARKERS)
        if in_entry and is_end:
            if last_entry_idx is not None:
                entry_line = out_lines[last_entry_idx].rstrip()
                entry_line = re.sub(r"\{\}(?=\}\})", "", entry_line)
                if entry_line.endswith("{}"):
                    entry_line = entry_line[:-2].rstrip()
                if not entry_line.endswith("}}"):
                    out_lines[last_entry_idx] = entry_line + "}}"
            in_entry = False
            last_entry_idx = None
        out_lines.append(line)
        if "\\glossentry" in line and "\\glossaryentrynumbers" in line:
            in_entry = True
            last_entry_idx = len(out_lines) - 1
            continue
        if in_entry and stripped:
            last_entry_idx = len(out_lines) - 1
    if in_entry and last_entry_idx is not None:
        entry_line = out_lines[last_entry_idx].rstrip()
        entry_line = re.sub(r"\{\}(?=\}\})", "", entry_line)
        if entry_line.endswith("{}"):
            entry_line = entry_line[:-2].rstrip()
        if not entry_line.endswith("}}"):
            out_lines[last_entry_idx] = entry_line + "}}"
    result = "\n".join(out_lines)
    if has_trailing_newline:
        result += "\n"
    if result == text:
        return False
    path.write_text(result, encoding="utf-8")
    return True


def latexmk_makeindex_command() -> str:
    """Return a makeindex command string suitable for latexmkrc."""
    tokens = [shlex.quote(token) for token in index_command_tokens()]
    return " ".join([*tokens, "%O", "-o", "%D", "%S"])


def latexmk_makeglossaries_command() -> str:
    """Return a makeglossaries command string suitable for latexmkrc."""
    tokens = [shlex.quote(token) for token in glossary_command_tokens()]
    return " ".join([*tokens, '"$base"'])


__all__ = [
    "glossary_command_tokens",
    "index_command_tokens",
    "is_available",
    "latexmk_makeglossaries_command",
    "latexmk_makeindex_command",
    "sanitize_glossary_output",
    "sanitize_xdy",
]
