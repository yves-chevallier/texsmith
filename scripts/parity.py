#!/usr/bin/env python3
"""Parity harness for the TeXSmith → TMark migration (plan task 4.1).

Renders every entry of ``tests/parity/corpus.yml`` (the examples' command lines
and every ``docs/**/*.md`` page) with the legacy ``html`` reader and, once the
CLI grows ``--reader``, with the ``tmark`` reader; normalises the ``.tex`` /
``.typ`` outputs; diffs them modulo ``tests/parity/allow.yml``.

Subcommands::

    parity.py baseline [--check]        legacy outputs → tests/parity/baseline/
    parity.py render --reader R --out D one reader, raw outputs, no diff
    parity.py diff                      both readers, allow-list, per-entry table
    parity.py pdf --entries ID...       build both sides, rasterise, pixel diff
    parity.py list                      corpus entries and which are runnable
    parity.py seed-cache                copy the DOI cache back into tests/parity/cache

Design: specs/migration/writers-and-passes.md §5.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import difflib
import fnmatch
from functools import cache
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
PARITY_DIR = ROOT / "tests" / "parity"
CORPUS_PATH = PARITY_DIR / "corpus.yml"
ALLOW_PATH = PARITY_DIR / "allow.yml"
BASELINE_DIR = PARITY_DIR / "baseline"
SEED_CACHE_DIR = PARITY_DIR / "cache"
BUILD_DIR = ROOT / "build" / "parity"

LEGACY_READER = "html"
READERS = ("html", "tmark")
BACKENDS = ("latex", "typst")
KNOWN_REQUIREMENTS = frozenset({"docker", "network", "fonts", "typst", "tectonic"})
RENDER_TIMEOUT = 3600  # nested snippet builds on a cold cache are slow

# Statuses shown in the per-entry tables.
IDENTICAL = "identical"
ALLOWED = "allow-listed"
DIFFERS = "differs"
SKIPPED = "skipped"
ERROR = "error"
MISSING = "missing-baseline"
FAILING = frozenset({DIFFERS, ERROR, MISSING})


class ParityError(Exception):
    """A configuration problem the user must fix (corpus, allow-list, toolchain)."""


# --------------------------------------------------------------------------- corpus


@dataclass(frozen=True)
class Entry:
    """One command line of the corpus."""

    entry_id: str
    cwd: str
    args: tuple[str, ...]
    backend: str
    requires: frozenset[str] = frozenset()

    @property
    def suffix(self) -> str:
        return ".typ" if self.backend == "typst" else ".tex"

    @property
    def stems(self) -> tuple[str, ...]:
        """Document stems the outputs may be named after (``<STEM>`` in the baseline).

        A multi-document build keeps its per-document stems (``\\input{a.tex}``
        must stay distinguishable from ``\\input{b.tex}``); only ``main`` is folded.
        """
        stems = [Path(arg).stem for arg in self.args if arg.lower().endswith((".md", ".html"))]
        return (*stems[:1], "main") if len(stems) == 1 else ("main",)

    def command(self, *, reader: str | None, out_dir: Path, build: bool = False) -> list[str]:
        argv = [*self.args, "-o", str(out_dir)]
        if reader is not None:
            argv += ["--reader", reader]
        if build:
            argv.append("--build")
        return argv


def _as_str_list(value: Any, *, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ParityError(f"corpus: {what} must be a list of strings, got {value!r}")
    return list(value)


def _requires(value: Any, *, what: str) -> frozenset[str]:
    items = _as_str_list(value or [], what=f"{what}.requires")
    unknown = set(items) - KNOWN_REQUIREMENTS
    if unknown:
        raise ParityError(
            f"corpus: {what} lists unknown requirements {sorted(unknown)}; "
            f"known: {sorted(KNOWN_REQUIREMENTS)}"
        )
    return frozenset(items)


def _example_entries(raw: Any) -> list[Entry]:
    if not isinstance(raw, list):
        raise ParityError("corpus: 'examples' must be a list")
    entries: list[Entry] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ParityError(f"corpus: examples[{index}] must be a mapping")
        entry_id = item.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            raise ParityError(f"corpus: examples[{index}] has no 'id'")
        what = f"examples[{entry_id}]"
        backend = item.get("backend")
        if backend not in BACKENDS:
            raise ParityError(f"corpus: {what}.backend must be one of {BACKENDS}, got {backend!r}")
        cwd = item.get("cwd")
        if not isinstance(cwd, str) or not (ROOT / cwd).is_dir():
            raise ParityError(f"corpus: {what}.cwd {cwd!r} is not a directory under the repository")
        args = _as_str_list(item.get("args"), what=f"{what}.args")
        if "--build" in args or "-M" in args or "--makefile-deps" in args:
            raise ParityError(f"corpus: {what}.args must not contain --build or -M")
        unknown_keys = set(item) - {"id", "cwd", "args", "backend", "requires"}
        if unknown_keys:
            raise ParityError(f"corpus: {what} has unknown keys {sorted(unknown_keys)}")
        entries.append(
            Entry(
                entry_id=entry_id,
                cwd=cwd,
                args=tuple(args),
                backend=backend,
                requires=_requires(item.get("requires"), what=what),
            )
        )
    return entries


def _docs_entries(raw: Any, root: Path) -> list[Entry]:
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise ParityError("corpus: 'docs' must be a mapping")
    pattern = raw.get("glob", "docs/**/*.md")
    cwd = raw.get("cwd", ".")
    base_args = _as_str_list(raw.get("args", []), what="docs.args")
    backends = _as_str_list(raw.get("backends", ["latex"]), what="docs.backends")
    excluded = {
        (item["path"] if isinstance(item, dict) else item)
        for item in (raw.get("exclude") or [])
        if isinstance(item, (str, dict))
    }
    per_path: dict[str, set[str]] = {}
    for index, rule in enumerate(raw.get("requires") or []):
        if not isinstance(rule, dict):
            raise ParityError(f"corpus: docs.requires[{index}] must be a mapping")
        needs = _requires(rule.get("requires"), what=f"docs.requires[{index}]")
        for path in _as_str_list(rule.get("paths"), what=f"docs.requires[{index}].paths"):
            if not (root / path).is_file():
                raise ParityError(f"corpus: docs.requires[{index}] names a missing page {path}")
            per_path.setdefault(path, set()).update(needs)

    entries: list[Entry] = []
    for page in sorted(root.glob(pattern)):
        rel = page.relative_to(root).as_posix()
        if rel in excluded:
            continue
        page_id = rel[: -len(".md")] if rel.endswith(".md") else rel
        needs = frozenset(per_path.get(rel, set()))
        for backend in backends:
            if backend not in BACKENDS:
                raise ParityError(f"corpus: docs.backends contains {backend!r}")
            args = [rel, *base_args]
            entry_id = page_id
            requires = needs
            if backend == "typst":
                args += ["--format", "typst"]
                entry_id = f"{page_id}@typst"
                requires = needs | {"typst"}
            entries.append(
                Entry(
                    entry_id=entry_id,
                    cwd=cwd,
                    args=tuple(args),
                    backend=backend,
                    requires=requires,
                )
            )
    return entries


def load_corpus(path: Path = CORPUS_PATH, *, root: Path = ROOT) -> list[Entry]:
    """Load and validate the corpus manifest; docs entries come from the glob."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ParityError(f"corpus: {path} must be a mapping with 'docs' and 'examples'")
    entries = _example_entries(raw.get("examples") or []) + _docs_entries(raw.get("docs"), root)
    seen: set[str] = set()
    for entry in entries:
        if entry.entry_id in seen:
            raise ParityError(f"corpus: duplicate entry id {entry.entry_id!r}")
        seen.add(entry.entry_id)
    return entries


def select_entries(entries: Iterable[Entry], patterns: Sequence[str] | None) -> list[Entry]:
    """Keep the entries whose id matches one of the ``--only`` globs (all when empty)."""
    if not patterns:
        return list(entries)
    return [
        entry
        for entry in entries
        if any(fnmatch.fnmatchcase(entry.entry_id, pattern) for pattern in patterns)
    ]


# --------------------------------------------------------------------- requirements


def _texsmith_home() -> Path:
    env_root = os.environ.get("TEXSMITH_HOME")
    return Path(env_root).expanduser() if env_root else Path.home() / ".texsmith"


def _user_texsmith_cache() -> Path:
    """The cache root texsmith would use without the harness (mirrors core/user_dir.py)."""
    env_cache = os.environ.get("TEXSMITH_CACHE_DIR")
    if env_cache:
        return Path(env_cache).expanduser()
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "texsmith"
    if os.environ.get("TEXSMITH_HOME"):
        return _texsmith_home() / "cache"
    return Path.home() / ".cache" / "texsmith"


def _playwright_browsers_dir() -> Path:
    """Where texsmith keeps (or would install) the Playwright Chromium build."""
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return _user_texsmith_cache() / "playwright" / "browsers"


@cache
def has_network() -> bool:
    """Cheap connectivity probe; ``PARITY_OFFLINE=1`` forces offline."""
    if os.environ.get("PARITY_OFFLINE"):
        return False
    for host in ("doi.org", "raw.githubusercontent.com"):
        try:
            with socket.create_connection((host, 443), timeout=3):
                return True
        except OSError:
            continue
    return False


def _run_quiet(argv: Sequence[str], *, timeout: float = 30) -> bool:
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


@cache
def has_docker() -> bool:
    return shutil.which("docker") is not None and _run_quiet(["docker", "info"])


@cache
def has_playwright_chromium() -> bool:
    """A Chromium build texsmith can launch without downloading one."""
    browsers = _playwright_browsers_dir()
    if not browsers.is_dir():
        return False
    probe = (
        "from playwright.sync_api import sync_playwright\n"
        "with sync_playwright() as p:\n"
        "    p.chromium.launch().close()\n"
    )
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(browsers))
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, timeout=60, check=False, env=env
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


@cache
def has_diagram_renderer() -> bool:
    """Any backend ``--diagrams-backend auto`` can use: Docker, Playwright, local CLIs."""
    if has_docker() or has_playwright_chromium():
        return True
    return any(shutil.which(tool) for tool in ("mmdc", "drawio")) or any(
        Path(hint).exists() for hint in ("/snap/bin/mmdc", "/snap/bin/drawio")
    )


@cache
def has_typst() -> bool:
    if shutil.which("typst"):
        return True
    return _run_quiet([sys.executable, "-c", "import typst"])


@cache
def has_tectonic() -> bool:
    """A LaTeX engine: system tectonic, the bundled download, or network to fetch it."""
    if shutil.which("tectonic"):
        return True
    bundled = _texsmith_home() / "bin"
    if bundled.is_dir() and any(bundled.glob("tectonic*")):
        return True
    return has_network()


@cache
def has_fonts() -> bool:
    """Font provisioning: a populated fonts dir, or network to download on first use."""
    fonts = _texsmith_home() / "fonts"
    if fonts.is_dir() and any(fonts.iterdir()):
        return True
    return has_network()


REQUIREMENT_CHECKS = {
    "docker": has_diagram_renderer,
    "network": has_network,
    "fonts": has_fonts,
    "typst": has_typst,
    "tectonic": has_tectonic,
}


def missing_requirements(
    entry: Entry, *, without: Iterable[str] = (), ignore: Iterable[str] = ()
) -> list[str]:
    """Requirements of ``entry`` that are unavailable (``without`` forces, ``ignore`` waives)."""
    forced = set(without)
    waived = set(ignore)
    missing: list[str] = []
    for requirement in sorted(entry.requires):
        if requirement in waived:
            continue
        if requirement in forced or not REQUIREMENT_CHECKS[requirement]():
            missing.append(requirement)
    return missing


# ------------------------------------------------------------------------ rendering


@cache
def cli_knows_reader() -> bool:
    """Whether the installed CLI accepts ``--reader`` (phase 3.2)."""
    try:
        import inspect

        from texsmith.ui.cli.commands.render import render
    except Exception:  # pragma: no cover - texsmith not importable
        return False
    return "reader" in inspect.signature(render).parameters


def reader_flag(reader: str) -> str | None:
    """The ``--reader`` value to pass, or ``None`` when the CLI has no such option."""
    if reader not in READERS:
        raise ParityError(f"unknown reader {reader!r}; expected one of {READERS}")
    if cli_knows_reader():
        return reader
    if reader != LEGACY_READER:
        raise ParityError(
            f"the installed texsmith CLI has no --reader option yet; only the legacy "
            f"{LEGACY_READER!r} reader can be rendered (requested {reader!r})"
        )
    return None


SHARED_CACHE_NAMESPACES = ("texmf", "playwright", "snippets")


def seed_cache(target: Path = BUILD_DIR / "cache", seed: Path = SEED_CACHE_DIR) -> Path:
    """Prepare the working cache: the committed seed plus links to the heavy user caches.

    ``tests/parity/cache`` (DOI lookups) is copied in. The TeX bundle, the
    Playwright Chromium build and the snippet cache are content-addressed and
    large, so they are linked from the user's own texsmith cache when present
    (a cold copy would otherwise be re-downloaded or rebuilt under build/).
    """
    target.mkdir(parents=True, exist_ok=True)
    if seed.is_dir():
        shutil.copytree(seed, target, dirs_exist_ok=True)
    user_cache = _user_texsmith_cache()
    if user_cache.resolve() != target.resolve():
        for namespace in SHARED_CACHE_NAMESPACES:
            source, link = user_cache / namespace, target / namespace
            if source.is_dir() and not link.exists() and not link.is_symlink():
                try:
                    link.symlink_to(source, target_is_directory=True)
                except OSError:
                    continue  # no symlink privilege (Windows): fall back to a cold cache
    return target


def render_env(cache_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "TEXSMITH_CACHE_DIR": str(cache_dir),
            "NO_COLOR": "1",
            "TERM": "dumb",
            "COLUMNS": "200",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    browsers = _playwright_browsers_dir()
    if browsers.is_dir():
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers))
    return env


@dataclass
class RenderResult:
    entry: Entry
    out_dir: Path
    returncode: int
    seconds: float
    log: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def outputs(self) -> list[Path]:
        """The ``.tex``/``.typ`` files at the top of the output directory."""
        return sorted(p for p in self.out_dir.glob(f"*{self.entry.suffix}") if p.is_file())

    def pdfs(self) -> list[Path]:
        return sorted(p for p in self.out_dir.rglob("*.pdf") if "assets" not in p.parts)


def render_entry(
    entry: Entry,
    *,
    reader: str,
    out_dir: Path,
    env: dict[str, str],
    build: bool = False,
) -> RenderResult:
    """Run one corpus command line into ``out_dir`` (cleared first)."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    argv = [
        sys.executable,
        "-c",
        "from texsmith.ui.cli.app import main; main()",
        *entry.command(reader=reader_flag(reader), out_dir=out_dir, build=build),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT / entry.cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RENDER_TIMEOUT,
            check=False,
        )
        returncode, log = completed.returncode, completed.stdout + completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode, log = 124, f"timeout after {exc.timeout}s"
    (out_dir / "_parity.log").write_text(
        f"$ (cd {entry.cwd} && texsmith {' '.join(argv[3:])})\n\n{log}", encoding="utf-8"
    )
    return RenderResult(entry, out_dir, returncode, time.monotonic() - started, log)


def render_many(
    entries: Sequence[Entry],
    *,
    reader: str,
    out_root: Path,
    jobs: int,
    build: bool = False,
) -> dict[str, RenderResult]:
    """Render entries in parallel; prints one progress line per entry."""
    env = render_env(seed_cache())
    results: dict[str, RenderResult] = {}
    total = len(entries)

    def work(entry: Entry) -> RenderResult:
        return render_entry(
            entry, reader=reader, out_dir=out_root / entry.entry_id, env=env, build=build
        )

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for index, result in enumerate(pool.map(work, entries), start=1):
            results[result.entry.entry_id] = result
            state = "ok" if result.ok else f"FAILED ({result.returncode})"
            print(
                f"[{index:>3}/{total}] {reader:<5} {result.entry.entry_id:<48} {state} {result.seconds:5.1f}s"
            )
    return results


# -------------------------------------------------------------------- normalisation

VERBATIM_ENVIRONMENTS = frozenset(
    {
        "verbatim",
        "Verbatim",
        "BVerbatim",
        "LVerbatim",
        "minted",
        "lstlisting",
        "code",
        "tscode",
        "comment",
        "filecontents",
        "filecontents*",
    }
)
_BEGIN_RE = re.compile(r"\\begin\{([^}]+)\}")
_END_RE = re.compile(r"\\end\{([^}]+)\}")
HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")
_CONVERTED_RE = re.compile(r"[\w./-]*\.converted/([\w.-]+)")
_INCLUDEGRAPHICS_RE = re.compile(r"(\\includegraphics(?:\[[^\]]*\])?\{)[^{}]*/([^{}/]+)\}")
_TYPST_IMAGE_RE = re.compile(r'(image\(\s*")[^"]*/([^"/]+)"')
_TSLEAD_RE = re.compile(r"^\s*\\providecommand\{\\tslead\}")
_TYP_COMMENT_RE = re.compile(r"^\s*//")
_TYP_MITEX_RE = re.compile(r'^\s*#import\s+"@preview/mitex')
# Lines around which a blank line carries no meaning in LaTeX: a block boundary
# (environment, sectioning, list item, table row or rule, float furniture).
_TEX_STRUCTURAL_RE = re.compile(
    r"^\\(?:begin|end)\{"
    r"|^\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\{"
    r"|^\\item\b"
    r"|^\\(?:toprule|midrule|bottomrule|cmidrule|hline|centering|caption|label|includegraphics"
    r"|vspace|maketitle|tableofcontents|clearpage|newpage|tsdivider|tsprogress|endfirsthead"
    r"|endhead|multicolumn|phantomsection|adjustbox|ifdefined|else|fi)\b"
    r"|^\{\\progressbar"
    r"|\\\\$"
)
_TEX_SPLIT_RE = re.compile(r"(\\vspace\{[^{}]*\}|\\begin\{center\})(\\begin\{)")
_TEX_ITEM_LABEL_RE = re.compile(r"^\\item\[\{ (.*) \}\]")
_TEX_PY_WHITESPACE = "\\PY{+w}{ }"
_TYP_FENCE_RE = re.compile(r"^\s*(`{3,})")
_TYP_TRAILING_COMMA_RE = re.compile(r",\s*\)")
_TYP_RAW_ARG_RE = re.compile(r"#(mi|mitex)\(```(.*?)```\)")


def find_comment(line: str) -> int:
    """Index of the first unescaped ``%`` in ``line``, or -1."""
    index = 0
    while True:
        index = line.find("%", index)
        if index < 0:
            return -1
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return index
        index += 1


def strip_tex_comments(text: str) -> str:
    """Drop ``%`` comments outside verbatim environments (tracked by an env stack)."""
    out: list[str] = []
    stack: list[str] = []
    for line in text.split("\n"):
        if stack:
            out.append(line)
            match = _END_RE.search(line)
            if match and match.group(1) == stack[-1]:
                stack.pop()
            continue
        index = find_comment(line)
        if index == 0 or (index >= 0 and not line[:index].strip()):
            continue
        kept = line[:index] if index >= 0 else line
        out.append(kept)
        match = _BEGIN_RE.search(kept)
        if match and match.group(1) in VERBATIM_ENVIRONMENTS:
            stack.append(match.group(1))
    return "\n".join(out)


def collapse_blank_lines(text: str) -> str:
    """Strip trailing whitespace, collapse blank runs to one, one newline at EOF."""
    lines = [line.rstrip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if not line and out and not out[-1]:
            continue
        out.append(line)
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n"


def _tex_lines(text: str) -> list[tuple[str, bool]]:
    """``(line, verbatim)`` pairs, tracking the same environment stack as the comment stripper."""
    out: list[tuple[str, bool]] = []
    stack: list[str] = []
    for line in text.split("\n"):
        if stack:
            out.append((line, True))
            match = _END_RE.search(line)
            if match and match.group(1) == stack[-1]:
                stack.pop()
            continue
        out.append((line, False))
        match = _BEGIN_RE.search(line)
        if match and match.group(1) in VERBATIM_ENVIRONMENTS:
            stack.append(match.group(1))
    return out


def tidy_tex_layout(text: str) -> str:
    """Layout-only normalisation outside verbatim environments (both sides).

    Leading indentation is dropped (TeX ignores it), ``\\vspace{…}\\begin{…}`` and
    ``\\begin{center}\\begin{…}`` are split onto two lines, ``\\item[{ x }]`` loses
    its padding, an inline Pygments group ``{\\ttfamily …`` closed on the next
    line is joined, ``\\PY{+w}{ }`` becomes a plain space, and a blank line next
    to a block boundary (environment, sectioning, ``\\item``, table row…) is
    dropped: none of these change what TeX typesets.
    """
    lines: list[tuple[str, bool]] = []
    for raw, verbatim in _tex_lines(text):
        if verbatim:
            lines.append((raw, True))
            continue
        line = raw.lstrip()
        if line.startswith("}") and lines and not lines[-1][1]:
            previous = lines[-1][0]
            if "{\\ttfamily " in previous and previous.count("{") > previous.count("}"):
                lines[-1] = (previous + line, False)
                continue
        line = _TEX_ITEM_LABEL_RE.sub(r"\\item[{\1}]", line)
        line = line.replace(_TEX_PY_WHITESPACE, " ")
        for piece in _TEX_SPLIT_RE.sub(r"\1\n\2", line).split("\n"):
            lines.append((piece, False))
    out: list[str] = []
    for index, (line, verbatim) in enumerate(lines):
        if not verbatim and not line.strip():
            before = lines[index - 1][0] if index > 0 else ""
            after = lines[index + 1][0] if index + 1 < len(lines) else ""
            if _TEX_STRUCTURAL_RE.search(before) or _TEX_STRUCTURAL_RE.search(after):
                continue
        out.append(line)
    return "\n".join(out)


def tidy_typ_layout(text: str) -> str:
    """Layout-only normalisation outside raw fences (both sides).

    Leading indentation is dropped, a line opening with ``]`` is joined to the
    previous one (trailing whitespace in a content block is trimmed by Typst),
    a trailing comma before ``)`` goes, ``#mi(```…```)`` becomes ``#mi(`…`)``
    and ``--``/``---`` become the en/em dash they typeset as.
    """
    out: list[str] = []
    fence = ""
    for raw in text.split("\n"):
        match = _TYP_FENCE_RE.match(raw)
        if fence:
            out.append(raw)
            if match and len(match.group(1)) >= len(fence) and not raw.strip(" `"):
                fence = ""
            continue
        if match:
            fence = match.group(1)
            out.append(raw)
            continue
        line = raw.lstrip()
        if line.startswith("]") and out:
            out[-1] += line
            continue
        line = _TYP_TRAILING_COMMA_RE.sub(")", line)
        line = _TYP_RAW_ARG_RE.sub(r"#\1(`\2`)", line)
        line = line.replace("---", "\u2014").replace("--", "\u2013")
        out.append(line)
    return "\n".join(out)


def replace_stems(text: str, stems: Iterable[str]) -> str:
    """``<stem>.bib``, ``inline-doi-<stem>.bib``, ``<stem>.tex`` … → ``<STEM>``."""
    for stem in stems:
        if not stem:
            continue
        pattern = re.compile(
            rf"(?<!\w){re.escape(stem)}(?=\.(?:bib|tex|typ|aux|pdf|d|bcf|log|toc)\b)"
        )
        text = pattern.sub("<STEM>", text)
    return text


def basename_assets(text: str) -> str:
    """``.converted/`` paths, remote and copied asset paths → basename."""
    text = _CONVERTED_RE.sub(r"\1", text)
    text = _INCLUDEGRAPHICS_RE.sub(r"\1\2}", text)
    return _TYPST_IMAGE_RE.sub(r'\1\2"', text)


def normalise_tex(text: str, stems: Iterable[str] = ()) -> str:
    text = text.replace("\r\n", "\n")
    text = strip_tex_comments(text)
    text = "\n".join(line for line in text.split("\n") if not _TSLEAD_RE.match(line))
    text = tidy_tex_layout(text)
    text = HASH_RE.sub("<HASH>", text)
    text = basename_assets(text)
    text = replace_stems(text, stems)
    return collapse_blank_lines(text)


def normalise_typ(text: str, stems: Iterable[str] = ()) -> str:
    text = text.replace("\r\n", "\n")
    lines = [
        line
        for line in text.split("\n")
        if not _TYP_COMMENT_RE.match(line) and not _TYP_MITEX_RE.match(line)
    ]
    text = tidy_typ_layout("\n".join(lines))
    text = HASH_RE.sub("<HASH>", text)
    text = basename_assets(text)
    text = replace_stems(text, stems)
    return collapse_blank_lines(text)


def normalise(text: str, suffix: str, stems: Iterable[str] = ()) -> str:
    return normalise_typ(text, stems) if suffix == ".typ" else normalise_tex(text, stems)


def extract_body(text: str) -> str:
    """The document body (between ``\\begin{document}`` and ``\\end{document}``).

    Slot fragments and ``.typ`` files have no envelope: the whole file is the body.
    """
    start = text.find("\\begin{document}")
    end = text.rfind("\\end{document}")
    if start < 0 or end < 0 or end < start:
        return text
    start = text.find("\n", start)
    body = text[start + 1 : end] if start >= 0 else ""
    return collapse_blank_lines(body)


# ----------------------------------------------------------------------- allow-list


@dataclass(frozen=True)
class AllowEntry:
    allow_id: str
    kind: str
    files: tuple[str, ...]
    reason: str
    expires: tuple[int, ...]
    rewrite_from: str = ""
    rewrite_to: str = ""
    pattern: re.Pattern[str] | None = None

    def applies_to(self, relpath: str) -> bool:
        return any(glob_to_regex(glob).match(relpath) for glob in self.files)


def parse_version(text: str) -> tuple[int, ...]:
    """Leading numeric components of a version (``0.6.1.dev7`` → ``(0, 6, 1)``)."""
    parts: list[int] = []
    for piece in str(text).split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    if not parts:
        raise ParityError(f"not a version: {text!r}")
    return tuple(parts)


@cache
def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """``**`` crosses ``/``, ``*`` and ``?`` do not; anchored at both ends."""
    out = ""
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out += "(?:.*/)?"
            index += 3
            continue
        if pattern.startswith("**", index):
            out += ".*"
            index += 2
            continue
        if char == "*":
            out += "[^/]*"
        elif char == "?":
            out += "[^/]"
        else:
            out += re.escape(char)
        index += 1
    return re.compile(f"^{out}$")


def texsmith_version() -> str:
    try:
        from importlib.metadata import version

        return version("texsmith")
    except Exception:  # pragma: no cover - not installed
        return "0.0.0"


def load_allow_list(
    path: Path = ALLOW_PATH, *, current_version: str | None = None
) -> list[AllowEntry]:
    """Load and validate ``allow.yml``; expired entries are an error."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else []
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ParityError(f"allow-list: {path} must be a list of entries")
    current = parse_version(current_version or texsmith_version())
    entries: list[AllowEntry] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        entries.append(_allow_entry(item, index=index, current=current, seen=seen))
    return entries


def _require_str(item: dict[str, Any], key: str, *, what: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ParityError(f"allow-list: {what}.{key} must be a non-empty string")
    return value


def _allow_entry(item: Any, *, index: int, current: tuple[int, ...], seen: set[str]) -> AllowEntry:
    if not isinstance(item, dict):
        raise ParityError(f"allow-list: entry {index} must be a mapping")
    allow_id = _require_str(item, "id", what=f"entry {index}")
    what = f"[{allow_id}]"
    if allow_id in seen:
        raise ParityError(f"allow-list: duplicate id {allow_id!r}")
    seen.add(allow_id)
    kind = _require_str(item, "kind", what=what)
    if kind not in {"rewrite", "hunk"}:
        raise ParityError(f"allow-list: {what}.kind must be 'rewrite' or 'hunk', got {kind!r}")
    files = item.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(f, str) for f in files):
        raise ParityError(f"allow-list: {what}.files must be a non-empty list of globs")
    reason = _require_str(item, "reason", what=what)
    expires = parse_version(_require_str(item, "expires", what=what))
    if current >= expires:
        raise ParityError(
            f"allow-list: {what} expired at {'.'.join(map(str, expires))} "
            f"(current {'.'.join(map(str, current))}); fix or remove it"
        )
    allowed_keys = {"id", "kind", "files", "reason", "expires"}
    if kind == "rewrite":
        allowed_keys |= {"from", "to"}
        rewrite_from = _require_str(item, "from", what=what)
        rewrite_to = item.get("to", "")
        if not isinstance(rewrite_to, str):
            raise ParityError(f"allow-list: {what}.to must be a string")
        pattern = None
    else:
        allowed_keys |= {"pattern"}
        rewrite_from = rewrite_to = ""
        try:
            pattern = re.compile(_require_str(item, "pattern", what=what), re.MULTILINE)
        except re.error as exc:
            raise ParityError(f"allow-list: {what}.pattern is not a valid regex: {exc}") from exc
    unknown = set(item) - allowed_keys
    if unknown:
        raise ParityError(f"allow-list: {what} has unknown keys {sorted(unknown)}")
    return AllowEntry(
        allow_id=allow_id,
        kind=kind,
        files=tuple(files),
        reason=reason,
        expires=expires,
        rewrite_from=rewrite_from,
        rewrite_to=rewrite_to,
        pattern=pattern,
    )


def apply_rewrites(text: str, relpath: str, allow: Iterable[AllowEntry]) -> str:
    for entry in allow:
        if entry.kind == "rewrite" and entry.applies_to(relpath):
            text = text.replace(entry.rewrite_from, entry.rewrite_to)
    return text


@dataclass(frozen=True)
class Hunk:
    header: str
    text: str  # the ``-``/``+`` lines, newline-joined, no trailing newline


def split_hunks(old: str, new: str, *, context: int = 0) -> list[Hunk]:
    """Hunks of the unified diff between two texts (zero context by default)."""
    diff = difflib.unified_diff(
        old.splitlines(), new.splitlines(), "legacy", "new", n=context, lineterm=""
    )
    hunks: list[Hunk] = []
    header = ""
    body: list[str] = []
    for line in diff:
        if line.startswith(("--- ", "+++ ")):
            continue
        if line.startswith("@@"):
            if header:
                hunks.append(Hunk(header, "\n".join(body)))
            header, body = line, []
            continue
        body.append(line)
    if header:
        hunks.append(Hunk(header, "\n".join(body)))
    return hunks


def hunk_allowed(hunk: Hunk, relpath: str, allow: Iterable[AllowEntry]) -> AllowEntry | None:
    """The first ``hunk`` allow-list entry matching this hunk, if any."""
    for entry in allow:
        if entry.kind != "hunk" or entry.pattern is None or not entry.applies_to(relpath):
            continue
        if entry.pattern.search(hunk.text):
            return entry
    return None


@dataclass
class FileVerdict:
    name: str
    hunks: int = 0
    allowed: int = 0
    diff: str = ""

    @property
    def status(self) -> str:
        if self.hunks == 0:
            return IDENTICAL
        return ALLOWED if self.allowed == self.hunks else DIFFERS


def compare_texts(
    old: str, new: str, *, relpath: str, allow: Sequence[AllowEntry] = ()
) -> FileVerdict:
    """Rewrite both sides, diff, classify every hunk against the allow-list."""
    old = apply_rewrites(old, relpath, allow)
    new = apply_rewrites(new, relpath, allow)
    hunks = split_hunks(old, new)
    verdict = FileVerdict(name=relpath, hunks=len(hunks))
    unlisted: list[str] = []
    for hunk in hunks:
        matched = hunk_allowed(hunk, relpath, allow)
        if matched is not None:
            verdict.allowed += 1
        else:
            unlisted.append(f"{hunk.header}\n{hunk.text}")
    if unlisted:
        verdict.diff = "\n".join(unlisted) + "\n"
    return verdict


# ------------------------------------------------------------------------- reports


@dataclass
class EntryReport:
    entry: Entry
    status: str
    detail: str = ""
    files: list[FileVerdict] = field(default_factory=list)

    @property
    def hunks(self) -> int:
        return sum(f.hunks for f in self.files)

    @property
    def allowed(self) -> int:
        return sum(f.allowed for f in self.files)


def print_table(reports: Sequence[EntryReport], *, title: str) -> None:
    print()
    print(title)
    print("-" * len(title))
    width = max((len(r.entry.entry_id) for r in reports), default=10)
    for report in reports:
        hunks = ""
        if report.status in {ALLOWED, DIFFERS}:
            hunks = f"{report.allowed}/{report.hunks} hunks allow-listed"
        detail = report.detail or hunks
        print(f"{report.entry.entry_id:<{width}}  {report.status:<16} {detail}")
    counts: dict[str, int] = {}
    for report in reports:
        counts[report.status] = counts.get(report.status, 0) + 1
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    print(f"\n{len(reports)} entries: {summary}")


def exit_code(reports: Sequence[EntryReport]) -> int:
    return 1 if any(r.status in FAILING for r in reports) else 0


def _write_diffs(reports: Sequence[EntryReport], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for report in reports:
        chunks = [f"### {f.name}\n{f.diff}" for f in report.files if f.diff]
        if chunks:
            target = out_dir / f"{report.entry.entry_id.replace('/', '__')}.diff"
            target.write_text("\n".join(chunks), encoding="utf-8")
            report.detail = (
                report.detail + " " if report.detail else ""
            ) + f"→ {target.relative_to(ROOT)}"


def normalised_outputs(result: RenderResult) -> dict[str, str]:
    """``{file name: normalised text}`` for a render result."""
    return {
        path.name: normalise(
            path.read_text(encoding="utf-8"), result.entry.suffix, result.entry.stems
        )
        for path in result.outputs()
    }


def skipped_report(entry: Entry, missing: Sequence[str]) -> EntryReport:
    return EntryReport(entry, SKIPPED, f"requires {', '.join(missing)}")


def error_report(result: RenderResult) -> EntryReport:
    tail = result.log.strip().splitlines()[-1:] if result.log.strip() else []
    detail = f"exit {result.returncode}"
    if tail:
        detail += f": {tail[0][:100]}"
    return EntryReport(
        result.entry, ERROR, f"{detail} (see {result.out_dir.relative_to(ROOT) / '_parity.log'})"
    )


# -------------------------------------------------------------------- subcommands


def _partition(
    entries: Sequence[Entry], *, without: Sequence[str], ignore: Sequence[str] = ()
) -> tuple[list[Entry], list[EntryReport]]:
    runnable: list[Entry] = []
    skipped: list[EntryReport] = []
    for entry in entries:
        missing = missing_requirements(entry, without=without, ignore=ignore)
        if missing:
            skipped.append(skipped_report(entry, missing))
        else:
            runnable.append(entry)
    return runnable, skipped


def cmd_list(args: argparse.Namespace) -> int:
    entries = select_entries(load_corpus(), args.only)
    print(f"{'id':<48} {'backend':<7} {'requires':<28} runnable")
    for entry in entries:
        missing = missing_requirements(entry, without=args.without)
        state = "yes" if not missing else f"no (missing {', '.join(missing)})"
        print(
            f"{entry.entry_id:<48} {entry.backend:<7} {','.join(sorted(entry.requires)) or '-':<28} {state}"
        )
    print(f"\n{len(entries)} entries; CLI knows --reader: {'yes' if cli_knows_reader() else 'no'}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    reader_flag(args.reader)  # fail early when the CLI cannot honour the reader
    entries = select_entries(load_corpus(), args.only)
    runnable, skipped = _partition(entries, without=args.without)
    out_root = Path(args.out).resolve()
    results = render_many(runnable, reader=args.reader, out_root=out_root, jobs=args.jobs)
    reports = [*skipped]
    for entry in runnable:
        result = results[entry.entry_id]
        if not result.ok:
            reports.append(error_report(result))
            continue
        reports.append(EntryReport(entry, "rendered", ", ".join(p.name for p in result.outputs())))
    print_table(
        reports,
        title=f"render --reader {args.reader} → {out_root.relative_to(ROOT) if out_root.is_relative_to(ROOT) else out_root}",
    )
    return exit_code(reports)


def _baseline_dir(entry: Entry) -> Path:
    return BASELINE_DIR / entry.entry_id


def _write_baseline(entry: Entry, files: dict[str, str]) -> None:
    target = _baseline_dir(entry)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name, text in files.items():
        (target / name).write_text(text, encoding="utf-8", newline="\n")


def _check_baseline(entry: Entry, files: dict[str, str]) -> EntryReport:
    target = _baseline_dir(entry)
    if not target.is_dir():
        return EntryReport(entry, MISSING, "run `parity.py baseline` to record it")
    committed = {p.name: p.read_text(encoding="utf-8") for p in target.glob(f"*{entry.suffix}")}
    report = EntryReport(entry, IDENTICAL)
    for name in sorted(set(files) | set(committed)):
        relpath = f"{entry.entry_id}/{name}"
        if name not in committed:
            report.files.append(FileVerdict(name, hunks=1, diff=f"new file {relpath}\n"))
            continue
        if name not in files:
            report.files.append(
                FileVerdict(name, hunks=1, diff=f"file no longer produced {relpath}\n")
            )
            continue
        report.files.append(compare_texts(committed[name], files[name], relpath=relpath))
    if any(f.hunks for f in report.files):
        report.status = DIFFERS
    return report


def cmd_baseline(args: argparse.Namespace) -> int:
    entries = select_entries(load_corpus(), args.only)
    runnable, skipped = _partition(entries, without=args.without, ignore=("typst",))
    results = render_many(
        runnable, reader=LEGACY_READER, out_root=BUILD_DIR / LEGACY_READER, jobs=args.jobs
    )
    reports: list[EntryReport] = [*skipped]
    for entry in runnable:
        result = results[entry.entry_id]
        if not result.ok:
            reports.append(error_report(result))
            continue
        files = normalised_outputs(result)
        if not files:
            reports.append(
                EntryReport(
                    entry, ERROR, f"no {entry.suffix} output in {result.out_dir.relative_to(ROOT)}"
                )
            )
            continue
        if args.check:
            reports.append(_check_baseline(entry, files))
        else:
            _write_baseline(entry, files)
            reports.append(EntryReport(entry, "written", ", ".join(sorted(files))))
    if args.check:
        _write_diffs(reports, BUILD_DIR / "check")
        print_table(reports, title="baseline --check (legacy reader vs tests/parity/baseline)")
    else:
        print_table(reports, title="baseline (legacy reader → tests/parity/baseline)")
        for report in reports:
            if report.status == SKIPPED and _baseline_dir(report.entry).is_dir():
                print(f"kept the committed baseline of skipped entry {report.entry.entry_id}")
    return exit_code(reports)


def cmd_diff(args: argparse.Namespace) -> int:
    allow = load_allow_list()
    reader_flag(args.reader_a)
    reader_flag(args.reader_b)
    entries = select_entries(load_corpus(), args.only)
    runnable, skipped = _partition(entries, without=args.without, ignore=("typst",))
    results_a = render_many(
        runnable, reader=args.reader_a, out_root=BUILD_DIR / args.reader_a, jobs=args.jobs
    )
    results_b = render_many(
        runnable, reader=args.reader_b, out_root=BUILD_DIR / args.reader_b, jobs=args.jobs
    )
    reports: list[EntryReport] = [*skipped]
    full_reports: list[EntryReport] = []
    for entry in runnable:
        result_a, result_b = results_a[entry.entry_id], results_b[entry.entry_id]
        if not result_a.ok:
            reports.append(error_report(result_a))
            continue
        if not result_b.ok:
            reports.append(error_report(result_b))
            continue
        files_a, files_b = normalised_outputs(result_a), normalised_outputs(result_b)
        body = EntryReport(entry, IDENTICAL)
        full = EntryReport(entry, IDENTICAL)
        for name in sorted(set(files_a) | set(files_b)):
            relpath = f"{entry.entry_id}/{name}"
            text_a, text_b = files_a.get(name, ""), files_b.get(name, "")
            body.files.append(
                compare_texts(
                    extract_body(text_a), extract_body(text_b), relpath=relpath, allow=allow
                )
            )
            full.files.append(compare_texts(text_a, text_b, relpath=relpath, allow=allow))
        for report in (body, full):
            statuses = {f.status for f in report.files}
            if DIFFERS in statuses:
                report.status = DIFFERS
            elif ALLOWED in statuses:
                report.status = ALLOWED
        reports.append(body)
        full_reports.append(full)
    _write_diffs(reports, BUILD_DIR / "diff" / "body")
    _write_diffs(full_reports, BUILD_DIR / "diff" / "full")
    print_table(reports, title=f"diff {args.reader_a} vs {args.reader_b} — document body (gating)")
    print_table(
        full_reports, title=f"diff {args.reader_a} vs {args.reader_b} — full file (informative)"
    )
    return exit_code(reports)


def cmd_seed_cache(_args: argparse.Namespace) -> int:
    source = BUILD_DIR / "cache" / "bibliography"
    target = SEED_CACHE_DIR / "bibliography"
    if not source.is_dir():
        print(f"nothing to seed: {source.relative_to(ROOT)} does not exist (run a render first)")
        return 1
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(source.glob("*.bib")):
        shutil.copy2(path, target / path.name)
        copied += 1
    print(f"seeded {copied} DOI cache entries into {target.relative_to(ROOT)}")
    return 0


# -------------------------------------------------------------------------- pdf


def _rasterise(pdf: Path, *, dpi: int) -> tuple[list[Any], list[str]]:
    """Grayscale page images and text layers of a PDF (pymupdf + Pillow)."""
    import fitz  # pymupdf
    from PIL import Image

    images: list[Any] = []
    texts: list[str] = []
    with fitz.open(pdf) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
            images.append(Image.frombytes("L", (pix.width, pix.height), pix.samples).copy())
            texts.append(page.get_text("text"))
    return images, texts


def _ink(image: Any) -> Any:
    """Binary ink mask (255 where darker than the paper), as an ``L`` image."""
    return image.point(lambda value: 255 if value < 200 else 0)


def _pad_to(image: Any, size: tuple[int, int], fill: int = 255) -> Any:
    from PIL import Image

    if image.size == size:
        return image
    canvas = Image.new("L", size, fill)
    canvas.paste(image, (0, 0))
    return canvas


@dataclass
class PageDiff:
    number: int
    ratio: float
    text_hunks: int
    overlay: Path | None = None


def compare_pages(
    legacy: Any,
    new: Any,
    *,
    number: int,
    text_hunks: int,
    overlay_path: Path,
    threshold: float,
) -> PageDiff:
    """Pixel-diff two page images after a one-pixel dilation of both sides."""
    from PIL import Image, ImageChops, ImageFilter

    size = (max(legacy.width, new.width), max(legacy.height, new.height))
    legacy, new = _pad_to(legacy, size), _pad_to(new, size)
    ink_a, ink_b = _ink(legacy), _ink(new)
    dilated_a = ink_a.filter(ImageFilter.MaxFilter(3))
    dilated_b = ink_b.filter(ImageFilter.MaxFilter(3))
    only_a = ImageChops.subtract(ink_a, dilated_b)  # legacy ink with no new ink nearby
    only_b = ImageChops.subtract(ink_b, dilated_a)
    changed = only_a.histogram()[255] + only_b.histogram()[255]
    ratio = changed / float(size[0] * size[1])
    page = PageDiff(number=number, ratio=ratio, text_hunks=text_hunks)
    if ratio > threshold or text_hunks:
        overlay = Image.new("RGB", size, (255, 255, 255))
        both = ImageChops.darker(ink_a, ink_b)
        overlay.paste((96, 96, 96), mask=both)
        overlay.paste((220, 0, 0), mask=only_a)
        overlay.paste((0, 160, 0), mask=only_b)
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        overlay.save(overlay_path)
        page.overlay = overlay_path
    return page


def compare_pdfs(
    legacy_pdf: Path, new_pdf: Path, *, out_dir: Path, dpi: int, threshold: float
) -> tuple[str, list[PageDiff], str]:
    """Return ``(status, pages, detail)`` for two PDFs."""
    images_a, texts_a = _rasterise(legacy_pdf, dpi=dpi)
    images_b, texts_b = _rasterise(new_pdf, dpi=dpi)
    if len(images_a) != len(images_b):
        return DIFFERS, [], f"page count {len(images_a)} vs {len(images_b)}"
    pages: list[PageDiff] = []
    for number, (image_a, image_b, text_a, text_b) in enumerate(
        zip(images_a, images_b, texts_a, texts_b, strict=True), start=1
    ):
        text_hunks = len(split_hunks(text_a, text_b))
        pages.append(
            compare_pages(
                image_a,
                image_b,
                number=number,
                text_hunks=text_hunks,
                overlay_path=out_dir / f"page-{number:03d}.png",
                threshold=threshold,
            )
        )
    worst = max(pages, key=lambda p: p.ratio, default=None)
    text_pages = sum(1 for p in pages if p.text_hunks)
    detail = (
        f"{len(pages)} pages, worst {worst.ratio * 100:.3f}% on page {worst.number}, "
        f"text differs on {text_pages} page(s)"
        if worst
        else "no pages"
    )
    status = DIFFERS if any(p.ratio > threshold for p in pages) else IDENTICAL
    return status, pages, detail


def cmd_pdf(args: argparse.Namespace) -> int:
    reader_flag(args.reader_a)
    reader_flag(args.reader_b)
    corpus = {entry.entry_id: entry for entry in load_corpus()}
    unknown = [entry_id for entry_id in args.entries if entry_id not in corpus]
    if unknown:
        raise ParityError(f"unknown corpus entries: {', '.join(unknown)}")
    entries = [corpus[entry_id] for entry_id in args.entries]
    for entry in entries:
        needed = "typst" if entry.backend == "typst" else "tectonic"
        if not REQUIREMENT_CHECKS[needed]():
            raise ParityError(f"{entry.entry_id}: {needed} is required to build its PDF")
    runnable, skipped = _partition(entries, without=args.without)
    pdf_root = BUILD_DIR / "pdf"
    results_a = render_many(
        runnable,
        reader=args.reader_a,
        out_root=pdf_root / args.reader_a,
        jobs=args.jobs,
        build=True,
    )
    results_b = render_many(
        runnable,
        reader=args.reader_b,
        out_root=pdf_root / args.reader_b,
        jobs=args.jobs,
        build=True,
    )
    reports: list[EntryReport] = [*skipped]
    summary: dict[str, Any] = {}
    for entry in runnable:
        result_a, result_b = results_a[entry.entry_id], results_b[entry.entry_id]
        if not result_a.ok:
            reports.append(error_report(result_a))
            continue
        if not result_b.ok:
            reports.append(error_report(result_b))
            continue
        pdfs_a, pdfs_b = result_a.pdfs(), result_b.pdfs()
        if not pdfs_a or not pdfs_b or len(pdfs_a) != len(pdfs_b):
            reports.append(EntryReport(entry, ERROR, f"pdf outputs {len(pdfs_a)} vs {len(pdfs_b)}"))
            continue
        status, details = IDENTICAL, []
        for pdf_a, pdf_b in zip(pdfs_a, pdfs_b, strict=True):
            out_dir = pdf_root / entry.entry_id / pdf_a.stem
            verdict, pages, detail = compare_pdfs(
                pdf_a, pdf_b, out_dir=out_dir, dpi=args.dpi, threshold=args.threshold
            )
            details.append(f"{pdf_a.name}: {detail}")
            summary[f"{entry.entry_id}/{pdf_a.name}"] = {
                "status": verdict,
                "pages": [
                    {
                        "page": p.number,
                        "ratio": p.ratio,
                        "text_hunks": p.text_hunks,
                        "overlay": str(p.overlay.relative_to(ROOT)) if p.overlay else None,
                    }
                    for p in pages
                ],
            }
            if verdict == DIFFERS:
                status = DIFFERS
        reports.append(EntryReport(entry, status, "; ".join(details)))
    pdf_root.mkdir(parents=True, exist_ok=True)
    (pdf_root / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print_table(
        reports,
        title=f"pdf {args.reader_a} (red) vs {args.reader_b} (green) — overlays under build/parity/pdf/",
    )
    return exit_code(reports)


# -------------------------------------------------------------------------- main


def _default_jobs() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--only",
        action="append",
        metavar="GLOB",
        help="restrict to entry ids matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--without",
        action="append",
        default=[],
        choices=sorted(KNOWN_REQUIREMENTS),
        metavar="REQ",
        help="treat requirement REQ as unavailable (entries needing it are skipped)",
    )
    parser.add_argument(
        "--jobs", type=int, default=_default_jobs(), help="parallel renders (default: %(default)s)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parity.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list corpus entries and whether they can run here")
    _add_common(p_list)
    p_list.set_defaults(func=cmd_list)

    p_baseline = sub.add_parser(
        "baseline",
        help="render the legacy reader into tests/parity/baseline (or --check against it)",
    )
    p_baseline.add_argument(
        "--check",
        action="store_true",
        help="re-render and diff against the committed baseline; exit 1 on drift",
    )
    _add_common(p_baseline)
    p_baseline.set_defaults(func=cmd_baseline)

    p_render = sub.add_parser("render", help="render every entry with one reader (raw outputs)")
    p_render.add_argument("--reader", choices=READERS, default=LEGACY_READER)
    p_render.add_argument("--out", required=True, metavar="DIR")
    _add_common(p_render)
    p_render.set_defaults(func=cmd_render)

    p_diff = sub.add_parser("diff", help="render both readers, diff modulo the allow-list")
    p_diff.add_argument("--reader-a", choices=READERS, default=LEGACY_READER)
    p_diff.add_argument("--reader-b", choices=READERS, default="tmark")
    _add_common(p_diff)
    p_diff.set_defaults(func=cmd_diff)

    p_pdf = sub.add_parser("pdf", help="build both sides and pixel-diff the PDFs")
    p_pdf.add_argument("--entries", nargs="+", required=True, metavar="ID")
    p_pdf.add_argument("--reader-a", choices=READERS, default=LEGACY_READER)
    p_pdf.add_argument("--reader-b", choices=READERS, default="tmark")
    p_pdf.add_argument("--dpi", type=int, default=100)
    p_pdf.add_argument(
        "--threshold",
        type=float,
        default=0.001,
        help="max fraction of differing pixels per page (default 0.1%%)",
    )
    _add_common(p_pdf)
    p_pdf.set_defaults(func=cmd_pdf)

    p_seed = sub.add_parser(
        "seed-cache", help="copy build/parity/cache/bibliography into tests/parity/cache"
    )
    p_seed.set_defaults(func=cmd_seed_cache)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ParityError as exc:
        print(f"parity: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
