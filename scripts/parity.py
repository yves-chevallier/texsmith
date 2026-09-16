#!/usr/bin/env python3
"""Regression harness over the TeXSmith corpus (``tests/parity/corpus.yml``).

It renders every entry of the corpus — the examples' command lines and every
``docs/**/*.md`` page — through the CLI and compares the normalised ``.tex`` /
``.typ`` against a committed baseline. Any unreviewed change to the rendered
output fails the gate; an intended one is re-recorded in a diff a human reads.

Subcommands::

    parity.py baseline [--check]        corpus outputs → tests/parity/baseline/
    parity.py render --out DIR          raw outputs, no diff
    parity.py pdf --baseline [--check]  built PDFs → tests/parity/pdf-baseline.json
    parity.py list                      corpus entries and which are runnable
    parity.py seed-cache                copy the DOI cache back into tests/parity/cache

A Markdown source has exactly one reader — the CLI has no ``--reader`` option —
so the harness pins nothing and never compares two readers. Every subcommand
measures one rendering against a committed record of the same rendering: a
difference is either a regression or a change its author re-records.

Design: specs/migration/writers-and-passes.md §5.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
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
BASELINE_DIR = PARITY_DIR / "baseline"
SEED_CACHE_DIR = PARITY_DIR / "cache"
PDF_BASELINE_PATH = PARITY_DIR / "pdf-baseline.json"
BUILD_DIR = ROOT / "build" / "parity"

BACKENDS = ("latex", "typst")
KNOWN_REQUIREMENTS = frozenset({"docker", "network", "fonts", "typst", "tectonic"})
RENDER_TIMEOUT = 3600  # nested snippet builds on a cold cache are slow

# Statuses shown in the per-entry tables.
IDENTICAL = "identical"
DIFFERS = "differs"
SKIPPED = "skipped"
ERROR = "error"
MISSING = "missing-baseline"
ORPHANED = "orphaned-baseline"
FAILING = frozenset({DIFFERS, ERROR, MISSING, ORPHANED})


class ParityError(Exception):
    """A configuration problem the user must fix (corpus, toolchain)."""


# corpus


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

    def command(self, *, out_dir: Path, build: bool = False) -> list[str]:
        argv = [*self.args, "-o", str(out_dir)]
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


# requirements


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


# rendering

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
    #: The bodies present the moment the command exited. Compared against
    #: :meth:`outputs` at the end of the run, it says whether a body that is
    #: missing was never written or was written and then removed by something
    #: outside the harness.
    produced: tuple[str, ...] = ()

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
        *entry.command(out_dir=out_dir, build=build),
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
    result = RenderResult(entry, out_dir, returncode, time.monotonic() - started, log)
    return replace(result, produced=tuple(path.name for path in result.outputs()))


RENDER_LOCK_PATH = BUILD_DIR / "render.lock"
#: The byte a Windows lock covers, past any pid the file will ever hold.
LOCK_BYTE = 1 << 16


@contextmanager
def render_lock() -> Iterator[None]:
    """Hold ``build/parity`` for one run at a time.

    Every entry renders into a directory named after its id, which the run
    clears before the command writes into it. Two runs in one checkout
    therefore delete each other's output: the one that read its directory
    after the other cleared it reports ``no .tex output`` for a different
    handful of entries every time, which reads exactly like a regression and
    is not one. The lock lives with the open file, so it is released when the
    process ends however it ends, and a run that finds it held says who holds
    it instead of racing.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    handle = RENDER_LOCK_PATH.open("a+", encoding="utf-8")
    try:
        _take_lock(handle)
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield
    finally:
        handle.close()


def _take_lock(handle: Any) -> None:
    """Lock ``handle`` for this process, or raise naming the run that holds it."""
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ModuleNotFoundError:  # pragma: no cover - Windows
            import msvcrt

            # A Windows lock covers a byte range, and a locked byte cannot be
            # read by anyone, this process included. The pid sits at the
            # start of the file and must stay readable (by the test, and by
            # the run that is refused), so the lock takes one byte far past
            # it; locking past the end of the file is allowed.
            handle.seek(LOCK_BYTE)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.seek(0)
        holder = handle.read().strip() or "another process"
        raise ParityError(
            f"another parity run (pid {holder}) is rendering into "
            f"{BUILD_DIR.relative_to(ROOT)}: the two would clear each other's output "
            "directories and report differences neither of them produced. Wait for it "
            "to finish."
        ) from exc


def render_many(
    entries: Sequence[Entry],
    *,
    out_root: Path,
    jobs: int,
    build: bool = False,
) -> dict[str, RenderResult]:
    """Render entries in parallel; prints one progress line per entry."""
    results: dict[str, RenderResult] = {}
    total = len(entries)

    with render_lock():
        env = render_env(seed_cache())

        def work(entry: Entry) -> RenderResult:
            return render_entry(entry, out_dir=out_root / entry.entry_id, env=env, build=build)

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            for index, result in enumerate(pool.map(work, entries), start=1):
                results[result.entry.entry_id] = result
                state = "ok" if result.ok else f"FAILED ({result.returncode})"
                print(
                    f"[{index:>3}/{total}] {result.entry.entry_id:<48} "
                    f"{state} {result.seconds:5.1f}s"
                )
    return results


# normalisation

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
    r"|thispagestyle|pagestyle"
    r"|vspace|maketitle|tableofcontents|clearpage|newpage|tsdivider|tsprogress|endfirsthead"
    r"|endhead|multicolumn|phantomsection|adjustbox|ifdefined|else|fi)\b"
    r"|^\{\\progressbar"
    r"|\\\\$"
)
_TEX_SPLIT_RE = re.compile(
    r"(\\vspace\{[^{}]*\}|\\begin\{center\}|\\end\{[a-zA-Z@*]+\})(\\(?:begin|end)\{)"
)
# A `\label{…}` closing a *sectioning* command: TeX ignores the line break
# before it, so putting it on its own line lets a label-only difference be a
# hunk of its own instead of merging with the heading it follows. A caption's
# label is deliberately left in place, so losing one stays visible.
_TEX_LABEL_SPLIT_RE = re.compile(
    r"^(\\(?:part|chapter|(?:sub)*section|paragraph|subparagraph)\*?\{.*\})"
    r"(\\label\{[^{}]*\})$"
)
_TEX_ITEM_LABEL_RE = re.compile(r"^\\item\[\{ (.*) \}\]")
_TEX_PY_WHITESPACE = "\\PY{+w}{ }"
_TYP_FENCE_RE = re.compile(r"^\s*(`{3,})")
_TYP_PRELUDE_RE = re.compile(r"^#let ts-[a-z0-9-]+")
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
    its padding, a trailing ``\\label{…}`` and a run of ``\\end{…}\\begin{…}`` are
    split off, an inline Pygments group ``{\\ttfamily …`` closed on the next
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
        line = _TEX_LABEL_SPLIT_RE.sub(r"\1\n\2", line)
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


def _typ_fence_closes(raw: str, match: re.Match[str]) -> bool:
    """Whether a backtick run ends a raw block rather than opening one.

    A closing fence carries nothing but the brackets that close the call it sits
    in — the tmark writer wraps a fence as ``#ts-code(…)[`` … ```` ```] ````, so
    ``]``, ``)`` and ``,`` after the backticks still close the block.
    """
    return not raw[match.end() :].strip(" \t)],")


def _typ_bracket_delta(line: str) -> int:
    """Net bracket depth a Typst line opens, ignoring brackets inside strings."""
    depth = 0
    in_string = False
    escape = False
    for char in line:
        if escape:
            escape = False
        elif char == "\\":
            escape = True
        elif char == '"':
            in_string = not in_string
        elif in_string:
            continue
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
    return depth


def strip_typst_prelude(text: str) -> str:
    """Drop the top-level ``#let ts-…`` bindings (both sides, outside raw fences).

    The tmark Typst writer inlines ``texsmith.typ`` — the ``#ts-…`` contract
    functions — at the top of every file until the module is copied next to the
    ``.typ`` (fragment-contracts.md §1, Typst column). They are definitions, not
    typeset content, and the legacy writer inlined the equivalent code at each
    use site instead; this is the Typst twin of the ``\\providecommand{\\tslead}``
    rule that writers-and-passes.md §5 already lists for LaTeX.
    """
    out: list[str] = []
    fence = ""
    depth = 0
    dropping = False
    for raw in text.split("\n"):
        match = _TYP_FENCE_RE.match(raw)
        if fence:
            out.append(raw)
            if match and len(match.group(1)) >= len(fence) and _typ_fence_closes(raw, match):
                fence = ""
            continue
        if dropping:
            depth += _typ_bracket_delta(raw)
            if depth <= 0:
                dropping = False
            continue
        if match:
            fence = match.group(1)
            out.append(raw)
            continue
        if _TYP_PRELUDE_RE.match(raw):
            depth = _typ_bracket_delta(raw)
            dropping = depth > 0
            continue
        out.append(raw)
    return "\n".join(out)


def tidy_typ_layout(text: str) -> str:
    """Layout-only normalisation outside raw fences (both sides).

    Leading indentation is dropped, a line opening with ``]`` is joined to the
    previous non-blank one and a blank line just after ``[`` is dropped (Typst
    trims the leading and trailing whitespace of a content block),
    a trailing comma before ``)`` goes, ``#mi(```…```)`` becomes ``#mi(`…`)``
    and ``--``/``---`` become the en/em dash they typeset as.
    """
    out: list[str] = []
    fence = ""
    for raw in text.split("\n"):
        match = _TYP_FENCE_RE.match(raw)
        if fence:
            out.append(raw)
            if match and len(match.group(1)) >= len(fence) and _typ_fence_closes(raw, match):
                fence = ""
            continue
        if match:
            fence = match.group(1)
            out.append(raw)
            continue
        line = raw.lstrip()
        if line.startswith("]"):
            while out and not out[-1].strip():
                out.pop()
            if out:
                out[-1] += line
                continue
        if not line and out and out[-1].endswith("["):
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
    from texsmith.core.conversion.typst import typst_prelude

    text = text.replace("\r\n", "\n")
    # The inlined library is one verbatim block: drop it before the comment
    # filter touches its lines, so its set and show rules go with its bindings.
    text = text.replace(typst_prelude(), "", 1)
    lines = [
        line
        for line in text.split("\n")
        if not _TYP_COMMENT_RE.match(line) and not _TYP_MITEX_RE.match(line)
    ]
    text = strip_typst_prelude("\n".join(lines))
    text = tidy_typ_layout(text)
    text = HASH_RE.sub("<HASH>", text)
    text = basename_assets(text)
    text = replace_stems(text, stems)
    return collapse_blank_lines(text)


def normalise(text: str, suffix: str, stems: Iterable[str] = ()) -> str:
    return normalise_typ(text, stems) if suffix == ".typ" else normalise_tex(text, stems)


# diffing


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


@dataclass
class FileVerdict:
    name: str
    hunks: int = 0
    diff: str = ""

    @property
    def status(self) -> str:
        return IDENTICAL if self.hunks == 0 else DIFFERS


def compare_texts(old: str, new: str, *, relpath: str) -> FileVerdict:
    """Diff the committed text against a fresh one; every hunk is a finding.

    There is no allow-list: both sides are the same rendering of the same
    source, so a hunk is either a regression or a change its author re-records
    with ``parity.py baseline``.
    """
    hunks = split_hunks(old, new)
    verdict = FileVerdict(name=relpath, hunks=len(hunks))
    if hunks:
        verdict.diff = "\n".join(f"{hunk.header}\n{hunk.text}" for hunk in hunks) + "\n"
    return verdict


# reports


@dataclass
class EntryReport:
    entry: Entry
    status: str
    detail: str = ""
    files: list[FileVerdict] = field(default_factory=list)

    @property
    def hunks(self) -> int:
        return sum(f.hunks for f in self.files)


def print_table(reports: Sequence[EntryReport], *, title: str) -> None:
    print()
    print(title)
    print("-" * len(title))
    width = max((len(r.entry.entry_id) for r in reports), default=10)
    for report in reports:
        hunks = f"{report.hunks} differing hunks" if report.status == DIFFERS else ""
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
    """Write this run's diffs, and only this run's.

    The directory is cleared first: it used to accumulate, so a later run that
    reported an entry identical left the previous run's diff file sitting next
    to the fresh ones, and reading them together showed differences no run had
    found.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
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


def no_output_report(result: RenderResult) -> EntryReport:
    """A render the CLI reported as successful that left no body behind.

    The command said it worked, so the log alone explains nothing: the report
    names what the directory does hold, which separates a body written under
    another name from a directory that stayed empty.
    """
    entry = result.entry
    try:
        present = sorted(path.name for path in result.out_dir.iterdir())
    except OSError:
        present = []
    held = ", ".join(name for name in present if name != "_parity.log") or "nothing"
    wrote = (
        f"the command wrote {', '.join(result.produced)}, which is gone"
        if result.produced
        else "the command wrote none"
    )
    return EntryReport(
        entry,
        ERROR,
        f"no {entry.suffix} output in {result.out_dir.relative_to(ROOT)}, which holds {held}; "
        f"{wrote} (see {result.out_dir.relative_to(ROOT) / '_parity.log'})",
    )


# subcommands


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
    print(f"\n{len(entries)} entries")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    entries = select_entries(load_corpus(), args.only)
    runnable, skipped = _partition(entries, without=args.without)
    out_root = Path(args.out).resolve()
    results = render_many(runnable, out_root=out_root, jobs=args.jobs)
    reports = [*skipped]
    for entry in runnable:
        result = results[entry.entry_id]
        if not result.ok:
            reports.append(error_report(result))
            continue
        reports.append(EntryReport(entry, "rendered", ", ".join(p.name for p in result.outputs())))
    print_table(
        reports,
        title=f"render → {out_root.relative_to(ROOT) if out_root.is_relative_to(ROOT) else out_root}",
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
    """Diff a fresh render against the committed one — every hunk is a finding.

    Both sides come from the same rendering, so there is no such thing as an
    intended difference here: a change is either a regression or a change the
    author re-records with ``parity.py baseline`` and a reviewer reads.
    """
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


def _orphaned_baselines(entries: Sequence[Entry]) -> list[EntryReport]:
    """Recorded renderings whose corpus entry is gone.

    ``--check`` re-renders what the corpus lists, so a baseline left behind by
    a deleted page is invisible to it: two pages removed with the Markdown
    extensions kept their committed ``.tex`` and ``.typ`` for the whole
    migration. Only meaningful over the whole corpus, so a ``--only`` run
    reports none.
    """
    known = {entry.entry_id for entry in entries}
    reports: list[EntryReport] = []
    for path in sorted(BASELINE_DIR.rglob("*")):
        if not path.is_dir() or not any(child.is_file() for child in path.iterdir()):
            continue
        entry_id = str(path.relative_to(BASELINE_DIR))
        if entry_id in known:
            continue
        reports.append(
            EntryReport(
                Entry(entry_id=entry_id, cwd=".", args=(), backend="latex"),
                ORPHANED,
                "no corpus entry renders this; delete it",
            )
        )
    return reports


def cmd_baseline(args: argparse.Namespace) -> int:
    entries = select_entries(load_corpus(), args.only)
    runnable, skipped = _partition(entries, without=args.without, ignore=("typst",))
    results = render_many(runnable, out_root=BUILD_DIR / "render", jobs=args.jobs)
    reports: list[EntryReport] = [*skipped]
    for entry in runnable:
        result = results[entry.entry_id]
        if not result.ok:
            reports.append(error_report(result))
            continue
        files = normalised_outputs(result)
        if not files:
            reports.append(no_output_report(result))
            continue
        if args.check:
            reports.append(_check_baseline(entry, files))
        else:
            _write_baseline(entry, files)
            reports.append(EntryReport(entry, "written", ", ".join(sorted(files))))
    if args.check:
        if not args.only:
            reports.extend(_orphaned_baselines(load_corpus()))
        _write_diffs(reports, BUILD_DIR / "check")
        print_table(reports, title="baseline --check (fresh render vs tests/parity/baseline)")
    else:
        print_table(reports, title="baseline (fresh render → tests/parity/baseline)")
        for report in reports:
            if report.status == SKIPPED and _baseline_dir(report.entry).is_dir():
                print(f"kept the committed baseline of skipped entry {report.entry.entry_id}")
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


# pdf


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


# pdf baseline

# The entries the nightly job guards: one acronym-heavy page, the counter
# contract, the index and the margin notes — the four the triage's §6 pixel diff
# already covered, and the four whose fragments are most easily broken — plus the
# French book, whose parts exercise the language-dependent part names the book
# template's table of contents has to measure and print.
PDF_BASELINE_ENTRIES = (
    "abbr",
    "book-fr",
    "box-drawing",
    "counters",
    "index",
    "marginnote",
    "nested-lists",
)
# Absolute tolerance on a page's ink coverage. A pixel-exact figure is not
# reproducible across machines (see `pdf_digest`), so a page passes when its
# text layer is identical and its ink moved by less than this.
INK_TOLERANCE = 0.002
_PAGE_TEXT_WS_RE = re.compile(r"\s+")


def page_text(text: str) -> str:
    """A page's text layer with every whitespace run collapsed to one space."""
    return _PAGE_TEXT_WS_RE.sub(" ", text).strip()


def pdf_digest(pdf: Path, *, dpi: int) -> list[dict[str, Any]]:
    """Per-page record of a built PDF: raster size, ink coverage, text layer.

    Deliberately **not** a hash of the page bitmap. A sha256 over the pixels is
    all-or-nothing, and three things under it are not pinned: tectonic fetches
    whatever TeX bundle is current, TeXSmith downloads its fonts on first use,
    and pymupdf's rasteriser changes its antialiasing between releases — any of
    the three flips every hash while the document is unchanged. So the committed
    record is what survives a toolchain bump: the page count, the text layer verbatim — which is also readable in a
    review diff, so a change to the rendering shows up as the changed sentence
    — the raster size, and the ink coverage within ``INK_TOLERANCE``.

    The cost is stated once here: a layout-only change that keeps the text and
    moves less ink than the tolerance (a figure shifted a few millimetres) is
    invisible to this gate.
    """
    images, texts = _rasterise(pdf, dpi=dpi)
    pages: list[dict[str, Any]] = []
    for image, text in zip(images, texts, strict=True):
        ink = _ink(image).histogram()[255] / float(image.width * image.height)
        pages.append(
            {"size": [image.width, image.height], "ink": round(ink, 5), "text": page_text(text)}
        )
    return pages


def compare_pdf_digest(
    recorded: Sequence[dict[str, Any]], fresh: Sequence[dict[str, Any]]
) -> tuple[str, str]:
    """``(status, detail)`` for one document's committed record against a fresh one."""
    if len(recorded) != len(fresh):
        return DIFFERS, f"page count {len(recorded)} vs {len(fresh)}"
    problems: list[str] = []
    for number, (old, new) in enumerate(zip(recorded, fresh, strict=True), start=1):
        if list(old["size"]) != list(new["size"]):
            problems.append(f"page {number}: raster {old['size']} → {new['size']}")
        if old["text"] != new["text"]:
            problems.append(f"page {number}: the text layer changed")
        elif abs(old["ink"] - new["ink"]) > INK_TOLERANCE:
            problems.append(
                f"page {number}: ink {old['ink']:.5f} → {new['ink']:.5f} "
                f"(tolerance {INK_TOLERANCE})"
            )
    if problems:
        return DIFFERS, "; ".join(problems)
    return IDENTICAL, f"{len(fresh)} pages, text identical, ink within {INK_TOLERANCE}"


def _pdf_baseline_entries(args: argparse.Namespace, corpus: dict[str, Entry]) -> list[Entry]:
    wanted = args.entries or list(PDF_BASELINE_ENTRIES)
    unknown = [entry_id for entry_id in wanted if entry_id not in corpus]
    if unknown:
        raise ParityError(f"unknown corpus entries: {', '.join(unknown)}")
    return [corpus[entry_id] for entry_id in wanted]


def cmd_pdf(args: argparse.Namespace) -> int:
    """Build the corpus' PDFs and record — or check — them against the committed digest."""
    if not args.baseline:
        raise ParityError(
            "pdf only runs as `pdf --baseline` (record) or `pdf --baseline --check` "
            "(compare against tests/parity/pdf-baseline.json)"
        )
    corpus = {entry.entry_id: entry for entry in load_corpus()}
    entries = _pdf_baseline_entries(args, corpus)
    _require_pdf_toolchain(entries)
    runnable, skipped = _partition(entries, without=args.without)
    pdf_root = BUILD_DIR / "pdf"
    results = render_many(runnable, out_root=pdf_root / "build", jobs=args.jobs, build=True)
    committed: dict[str, Any] = {}
    if args.check:
        if not PDF_BASELINE_PATH.is_file():
            raise ParityError(
                f"{PDF_BASELINE_PATH.relative_to(ROOT)} does not exist; "
                f"record it with `parity.py pdf --baseline`"
            )
        stored = json.loads(PDF_BASELINE_PATH.read_text(encoding="utf-8"))
        if stored.get("dpi") != args.dpi:
            raise ParityError(
                f"the committed pdf baseline was recorded at {stored.get('dpi')} dpi, "
                f"not {args.dpi}; pass --dpi {stored.get('dpi')} or re-record it"
            )
        committed = stored.get("documents") or {}

    reports: list[EntryReport] = [*skipped]
    documents: dict[str, Any] = {}
    for entry in runnable:
        result = results[entry.entry_id]
        if not result.ok:
            reports.append(error_report(result))
            continue
        pdfs = result.pdfs()
        if not pdfs:
            reports.append(EntryReport(entry, ERROR, "no pdf output"))
            continue
        status, details = IDENTICAL, []
        for pdf in pdfs:
            name = f"{entry.entry_id}/{pdf.name}"
            pages = pdf_digest(pdf, dpi=args.dpi)
            documents[name] = pages
            if not args.check:
                details.append(f"{pdf.name}: {len(pages)} pages")
                continue
            if name not in committed:
                status = MISSING
                details.append(f"{pdf.name}: not in the committed record")
                continue
            verdict, detail = compare_pdf_digest(committed[name], pages)
            details.append(f"{pdf.name}: {detail}")
            if verdict == DIFFERS:
                status = DIFFERS
        reports.append(
            EntryReport(entry, "recorded" if not args.check else status, "; ".join(details))
        )

    pdf_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "dpi": args.dpi,
        "ink_tolerance": INK_TOLERANCE,
        "documents": documents,
    }
    if args.check:
        (pdf_root / "digest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print_table(
            reports,
            title=f"pdf --baseline --check (fresh build vs {PDF_BASELINE_PATH.relative_to(ROOT)})",
        )
    else:
        PDF_BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print_table(
            reports,
            title=f"pdf --baseline (fresh build → {PDF_BASELINE_PATH.relative_to(ROOT)})",
        )
    return exit_code(reports)


def _require_pdf_toolchain(entries: Sequence[Entry]) -> None:
    for entry in entries:
        needed = "typst" if entry.backend == "typst" else "tectonic"
        if not REQUIREMENT_CHECKS[needed]():
            raise ParityError(f"{entry.entry_id}: {needed} is required to build its PDF")


# main


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
        help="render every corpus entry into tests/parity/baseline (or --check against it)",
        description=(
            "Record, or check, the regression baseline: the normalised .tex/.typ every "
            "corpus entry renders to. Recording rewrites tests/parity/baseline/<id>/, "
            "which is committed, so an intended change to the rendered output lands in a "
            "review a human reads. --check re-renders and fails on any difference: both "
            "sides are the same rendering of the same source, so there is no such thing "
            "as an intended difference here and no allow-list to record one."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_baseline.add_argument(
        "--check",
        action="store_true",
        help="re-render and diff against the committed baseline; exit 1 on drift",
    )
    _add_common(p_baseline)
    p_baseline.set_defaults(func=cmd_baseline)

    p_render = sub.add_parser(
        "render", help="render every entry into a directory (raw outputs, no comparison)"
    )
    p_render.add_argument("--out", required=True, metavar="DIR")
    _add_common(p_render)
    p_render.set_defaults(func=cmd_render)

    p_pdf = sub.add_parser(
        "pdf",
        help="build the PDFs and record (or --check) tests/parity/pdf-baseline.json",
        description=(
            "Build the PDFs with the full toolchain and record each page's text layer, "
            "raster size and ink coverage into tests/parity/pdf-baseline.json, which is "
            "committed; --baseline --check rebuilds and compares against it. The default "
            f"entry set is {' '.join(PDF_BASELINE_ENTRIES)}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_pdf.add_argument(
        "--entries",
        nargs="+",
        metavar="ID",
        help=f"corpus entries to build (default: {' '.join(PDF_BASELINE_ENTRIES)})",
    )
    p_pdf.add_argument(
        "--baseline",
        action="store_true",
        help="record the built PDFs into tests/parity/pdf-baseline.json (required)",
    )
    p_pdf.add_argument(
        "--check",
        action="store_true",
        help="with --baseline: compare against the committed record instead of rewriting it",
    )
    p_pdf.add_argument("--dpi", type=int, default=100)
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
