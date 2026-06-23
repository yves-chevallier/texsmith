#!/usr/bin/env python3
"""Golden harness for the TeXSmith IR migration (Phase 0).

This tool captures the LaTeX (``.tex`` / ``.sty``) produced *today* by every
example, snippet and MkDocs page, and provides a normalised, reproducible
``diff`` against a committed baseline. The examples are the source of truth for
the rendered output, so a zero diff before/after a migration step proves
iso-rendering.

Only the **deterministic text artefacts** (``.tex`` and ``.sty``) are
snapshotted. PDFs are intentionally out of scope: the ``.tex`` is deterministic,
the PDF is not and would require a TeX toolchain. Each case therefore runs the
*same* CLI command as its ``Makefile`` but **without** ``--build`` and
``--engine`` (no PDF compilation).

Usage::

    python refactoring/tools/snapshot.py capture            # write baseline
    python refactoring/tools/snapshot.py diff               # compare to baseline
    python refactoring/tools/snapshot.py capture --only paper math
    python refactoring/tools/snapshot.py diff --skip-docker
    python refactoring/tools/snapshot.py list                # list known cases

``diff`` exits non-zero when any captured artefact differs from the baseline.

See ``refactoring/tools/README.md`` for the full coverage / normalisation
contract.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
import difflib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


# --------------------------------------------------------------------------- #
# Repository layout
# --------------------------------------------------------------------------- #

# refactoring/tools/snapshot.py -> repo root is two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "examples"
BASELINE_ROOT = REPO_ROOT / "refactoring" / "baseline"

# Artefacts we snapshot: the deterministic LaTeX text. Everything else (PDF,
# PNG, fonts, .aux, logs, .latexmkrc, JSON manifests) is volatile or binary and
# is deliberately excluded.
SNAPSHOT_SUFFIXES = (".tex", ".sty")


# --------------------------------------------------------------------------- #
# Normalisation of volatile fields
#
# Every rule is applied (in order) to each captured text artefact BEFORE it is
# written/compared. Two runs over unchanged code MUST yield byte-identical
# normalised output. Each rule documents *what* volatile source it neutralises.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NormalisationRule:
    """A documented regex substitution applied before comparison."""

    name: str
    why: str
    pattern: re.Pattern[str]
    replacement: str


# English + French month names produced by ``core/document_date.py`` long-form
# rendering (``date: today`` / ``date: commit`` / ISO dates resolved at render).
_EN_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_FR_MONTHS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|"
    "octobre|novembre|décembre|decembre"
)

NORMALISATION_RULES: tuple[NormalisationRule, ...] = (
    NormalisationRule(
        name="latex-today",
        why=r"`\today` expands to the build date inside TeX; volatile.",
        pattern=re.compile(r"\\today\b"),
        replacement="<DATE>",
    ),
    NormalisationRule(
        name="english-long-date",
        why=(
            "`date: today`/ISO dates render as 'March 15, 2025' via "
            "document_date.py; the absolute date is volatile when 'today'."
        ),
        pattern=re.compile(rf"\b(?:{_EN_MONTHS})\s+\d{{1,2}},\s+\d{{4}}\b"),
        replacement="<DATE>",
    ),
    NormalisationRule(
        name="french-long-date",
        why=(
            "French locale renders dates as '5 mars 2026' / '1er mars 2026' "
            "(document_date.py); volatile when 'today'."
        ),
        pattern=re.compile(rf"\b\d{{1,2}}(?:er)?\s+(?:{_FR_MONTHS})\s+\d{{4}}\b"),
        replacement="<DATE>",
    ),
    NormalisationRule(
        name="iso-timestamp",
        why="ISO 8601 timestamps (e.g. remote-asset 'checked_at') are volatile.",
        pattern=re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"),
        replacement="<TIMESTAMP>",
    ),
    NormalisationRule(
        name="git-describe-version",
        why=(
            "`version: git` expands to `git describe --tags --dirty` "
            "(git_version.py): e.g. v0.3.1-5-gabcdef-dirty; volatile per commit."
        ),
        pattern=re.compile(r"\bv\d+\.\d+\.\d+(?:-[0-9]+-g[0-9a-f]+)?(?:-dirty)?\b"),
        replacement="<GITVERSION>",
    ),
    NormalisationRule(
        name="asset-hash-filename",
        why=(
            "Converted/snippet assets are content-addressed: '<name>-<sha>.<ext>' "
            "or bare '<sha64>.<ext>'. The hash can shift if the asset pipeline "
            "changes; we compare structure, not the hash. The .tex still proves "
            "the *reference* is emitted at the right place."
        ),
        # name-prefixed hash, e.g. snippet-<64hex>.pdf -> snippet-<HASH>.pdf
        pattern=re.compile(r"([A-Za-z0-9_]+)-[0-9a-f]{32,64}(\.[A-Za-z0-9]+)"),
        replacement=r"\1-<HASH>\2",
    ),
    NormalisationRule(
        name="bare-hash-filename",
        why="Bare content-addressed asset filenames '<sha64>.<ext>'.",
        pattern=re.compile(r"\b[0-9a-f]{64}(\.[A-Za-z0-9]+)"),
        replacement=r"<HASH>\1",
    ),
)


def _normalise_absolute_paths(text: str) -> str:
    """Replace absolute paths that may leak into artefacts.

    Implemented in code (not a static regex) because the placeholders depend on
    the live repository / home / temp roots. Applied before the regex rules.
    """
    replacements = (
        (str(REPO_ROOT), "<REPO>"),
        (str(Path.home()), "<HOME>"),
        (tempfile.gettempdir(), "<TMP>"),
    )
    for needle, placeholder in replacements:
        if needle and needle != "/":
            text = text.replace(needle, placeholder)
    return text


def normalise(text: str) -> str:
    """Apply every normalisation rule to ``text``."""
    text = _normalise_absolute_paths(text)
    for rule in NORMALISATION_RULES:
        text = rule.pattern.sub(rule.replacement, text)
    return text


# --------------------------------------------------------------------------- #
# Case configuration (derived from examples/*/Makefile)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Case:
    """A single snapshot case.

    ``directory`` is relative to ``examples/``. ``args`` is the full CLI
    argument vector passed to ``texsmith`` (inputs + ``-t`` + ``-a`` flags),
    exactly as the Makefile builds it minus ``--build``/``--engine``.
    """

    name: str
    directory: str
    args: tuple[str, ...]
    requires_docker: bool = False
    note: str = ""

    @property
    def cwd(self) -> Path:
        return EXAMPLES_ROOT / self.directory


@dataclass(frozen=True)
class MkdocsCase:
    """A MkDocs build case (``mkdocs build`` instead of a direct CLI call)."""

    name: str
    directory: str
    # Subtree under the example directory that holds generated artefacts.
    output_subdir: str
    requires_docker: bool = False
    note: str = ""

    @property
    def cwd(self) -> Path:
        return EXAMPLES_ROOT / self.directory


# Derived 1:1 from examples/*/Makefile. ``--build`` and ``$(TEXSMITH_ENGINE)``
# are intentionally dropped (we only want the deterministic .tex/.sty).
CLI_CASES: tuple[Case, ...] = (
    Case("abbr", "abbr", ("abbreviations.md", "-tarticle")),
    # admonition: the Makefile `latex` target uses -acallouts.style=fancy.
    Case("admonition", "admonition", ("admonition.md", "-tarticle", "-acallouts.style=fancy")),
    Case("booby", "booby", ("booby.md", "-tarticle")),
    Case("book", "book", ("book.md", "book.bib", "-tbook", "-abibliography_style=numeric")),
    Case("code-block", "code", ("code-block.md",)),
    Case("code-inline", "code", ("code-inline.md",)),
    Case("colorful", "colorful", ("colorful.md",)),
    Case(
        "diagrams",
        "diagrams",
        ("diagrams.md", "-tarticle"),
        requires_docker=True,
        note="drawio/SVG conversion may require Docker when no playwright/cairosvg backend.",
    ),
    Case("dialects", "dialects", ("dialects.md", "-tarticle")),
    # emoji: default + black variants are engine-agnostic for .tex; the `color`
    # variant only exists for lualatex builds, so it is not a distinct .tex case.
    Case("emoji-default", "emoji", ("emoji.md", "-tarticle")),
    Case("emoji-bw", "emoji", ("emoji.md", "-tarticle", "-afonts.emoji=black")),
    Case("fonts", "fonts", ("fonts.md", "-tarticle")),
    Case("index", "index", ("index.md", "-tarticle")),
    Case("letter-din", "letter", ("letter.md", "-tletter", "-aformat=din")),
    Case("letter-sn", "letter", ("letter.md", "-tletter", "-aformat=sn")),
    Case("letter-nf", "letter", ("letter.md", "-tletter", "-aformat=nf")),
    Case("marginnote", "marginnote", ("marginnote.md", "-tarticle")),
    Case("markdown", "markdown", ("features.md", "-tarticle")),
    Case(
        "math",
        "math",
        ("math.md", "-tarticle", r"-apress.override.preamble=\usepackage{csquotes}"),
    ),
    Case(
        "mermaid",
        "mermaid",
        ("mermaid.md", "-tarticle"),
        requires_docker=True,
        note="mermaid rendering may require Docker when no playwright backend.",
    ),
    Case("multi-document", "multi-document", ("a.md", "b.md", "c.md", "config.yml", "-tarticle")),
    Case("paper", "paper", ("cheese.md", "cheese.bib", "-tarticle")),
    Case(
        "progressbar",
        "progressbar",
        ("progressbar.md", "-tarticle", r"-apress.override.preamble=\usepackage{progressbar}"),
    ),
    # recipe uses a local template (-t.) resolved against the example cwd.
    Case("recipe", "recipe", ("cake.yml", "-t.")),
    Case("snippet", "snippet", ("docs/index.md", "-tarticle")),
)

MKDOCS_CASES: tuple[MkdocsCase, ...] = (
    # Only examples/mkdocs wires the texsmith plugin (build_dir: press).
    # examples/paper/mkdocs.yml has NO texsmith plugin, so it produces no .tex
    # and is covered instead by the `paper` CLI case above.
    MkdocsCase("mkdocs", "mkdocs", output_subdir="press"),
)


# --------------------------------------------------------------------------- #
# Capture / collection
# --------------------------------------------------------------------------- #


@dataclass
class CaptureResult:
    """Outcome of running one case."""

    name: str
    status: str  # "captured" | "skipped" | "failed"
    files: dict[str, str] = field(default_factory=dict)  # rel-path -> normalised text
    reason: str = ""


def _texsmith_cmd() -> list[str]:
    """Resolve how to invoke the CLI.

    Prefer ``uv run texsmith`` (matches the Makefiles); fall back to the current
    interpreter's module entry point if ``uv`` is unavailable.
    """
    if shutil.which("uv"):
        return ["uv", "run", "texsmith"]
    return [sys.executable, "-m", "texsmith"]


def _collect_artifacts(root: Path) -> dict[str, str]:
    """Read + normalise every snapshot artefact under ``root``.

    Returns a mapping of POSIX relative path -> normalised text. ``fonts/``
    subtrees are skipped (binary font files only; no .tex/.sty live there).
    """
    collected: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in SNAPSHOT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("fonts/") or "/fonts/" in rel:
            continue
        raw = path.read_text(encoding="utf-8", errors="surrogateescape")
        collected[rel] = normalise(raw)
    return collected


def _run_cli_case(case: Case, *, env: dict[str, str]) -> CaptureResult:
    out_dir = Path(tempfile.mkdtemp(prefix=f"texsmith-snap-{case.name}-"))
    try:
        cmd = [*_texsmith_cmd(), *case.args, f"-o{out_dir}"]
        proc = subprocess.run(
            cmd,
            cwd=case.cwd,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            reason = (proc.stderr or proc.stdout or "").strip()[-2000:]
            return CaptureResult(case.name, "failed", reason=reason)
        files = _collect_artifacts(out_dir)
        if not files:
            return CaptureResult(
                case.name,
                "failed",
                reason="no .tex/.sty artefacts produced",
            )
        return CaptureResult(case.name, "captured", files=files)
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _run_mkdocs_case(case: MkdocsCase, *, env: dict[str, str]) -> CaptureResult:
    out_root = case.cwd / case.output_subdir
    site_dir = case.cwd / "site"
    # Clean prior build so collection is exact.
    shutil.rmtree(out_root, ignore_errors=True)
    shutil.rmtree(site_dir, ignore_errors=True)
    build_env = dict(env)
    # Ensure no PDF build: the Makefile sets TEXSMITH_BUILD=1 to compile; we omit it.
    build_env.pop("TEXSMITH_BUILD", None)
    cmd = [*_mkdocs_cmd(), "build"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=case.cwd,
            env=build_env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            reason = (proc.stderr or proc.stdout or "").strip()[-2000:]
            return CaptureResult(case.name, "failed", reason=reason)
        if not out_root.exists():
            return CaptureResult(case.name, "failed", reason=f"{case.output_subdir}/ not produced")
        files = _collect_artifacts(out_root)
        if not files:
            return CaptureResult(case.name, "failed", reason="no .tex/.sty artefacts produced")
        return CaptureResult(case.name, "captured", files=files)
    finally:
        shutil.rmtree(out_root, ignore_errors=True)
        shutil.rmtree(site_dir, ignore_errors=True)


def _mkdocs_cmd() -> list[str]:
    if shutil.which("uv"):
        return ["uv", "run", "mkdocs"]
    return [sys.executable, "-m", "mkdocs"]


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def _docker_available() -> bool:
    """Report Docker availability.

    Prefers the project helper ``texsmith.adapters.docker.is_docker_available``
    (the single source of truth used by the diagram pipeline). When TeXSmith is
    not importable in the current interpreter (e.g. the script was launched with
    a bare ``python`` rather than ``uv run python``), fall back to probing the
    ``docker`` executable directly so the skip logic stays correct.
    """
    try:
        from texsmith.adapters.docker import is_docker_available

        return bool(is_docker_available())
    except ImportError:
        pass
    except Exception:
        return False
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return False
    try:
        proc = subprocess.run(
            [docker_bin, "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return proc.returncode == 0


def _selected_cases(
    only: Sequence[str] | None,
) -> tuple[list[Case], list[MkdocsCase]]:
    cli = list(CLI_CASES)
    mk = list(MKDOCS_CASES)
    if only:
        wanted = set(only)
        cli = [c for c in cli if c.name in wanted or c.directory in wanted]
        mk = [c for c in mk if c.name in wanted or c.directory in wanted]
    return cli, mk


def _run_all(
    *,
    only: Sequence[str] | None,
    skip_docker: bool,
) -> list[CaptureResult]:
    cli_cases, mkdocs_cases = _selected_cases(only)
    docker_ok = _docker_available()
    if skip_docker:
        docker_ok = False

    env = dict(os.environ)
    results: list[CaptureResult] = []

    for case in cli_cases:
        if case.requires_docker and not docker_ok:
            results.append(
                CaptureResult(
                    case.name,
                    "skipped",
                    reason="requires-docker (Docker unavailable or --skip-docker)",
                )
            )
            continue
        print(f"  running {case.name} ...", flush=True)
        results.append(_run_cli_case(case, env=env))

    for case in mkdocs_cases:
        if case.requires_docker and not docker_ok:
            results.append(CaptureResult(case.name, "skipped", reason="requires-docker"))
            continue
        print(f"  running {case.name} (mkdocs build) ...", flush=True)
        results.append(_run_mkdocs_case(case, env=env))

    return results


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def _baseline_dir(name: str) -> Path:
    return BASELINE_ROOT / name


def cmd_capture(args: argparse.Namespace) -> int:
    results = _run_all(only=args.only, skip_docker=args.skip_docker)
    failures = [r for r in results if r.status == "failed"]

    for result in results:
        if result.status != "captured":
            continue
        target = _baseline_dir(result.name)
        shutil.rmtree(target, ignore_errors=True)
        for rel, text in result.files.items():
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

    _print_summary("capture", results)
    if failures:
        print(f"\nERROR: {len(failures)} case(s) failed during capture.", file=sys.stderr)
        return 1
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    results = _run_all(only=args.only, skip_docker=args.skip_docker)
    failures = [r for r in results if r.status == "failed"]
    drifted: list[str] = []

    for result in results:
        if result.status != "captured":
            continue
        baseline = _baseline_dir(result.name)
        if not baseline.exists():
            drifted.append(result.name)
            print(f"\n[{result.name}] NO BASELINE — run `capture` first.")
            continue

        expected: dict[str, str] = {}
        for path in sorted(baseline.rglob("*")):
            if path.is_file() and path.suffix in SNAPSHOT_SUFFIXES:
                rel = path.relative_to(baseline).as_posix()
                expected[rel] = path.read_text(encoding="utf-8", errors="surrogateescape")

        got = result.files
        case_drift = _report_case_diff(result.name, expected, got)
        if case_drift:
            drifted.append(result.name)

    _print_summary("diff", results)

    if drifted:
        print(f"\nDIFF: {len(drifted)} case(s) drifted: {', '.join(sorted(drifted))}")
    if failures:
        print(f"FAILED: {len(failures)} case(s) failed to render.", file=sys.stderr)

    return 1 if (drifted or failures) else 0


def _report_case_diff(name: str, expected: dict[str, str], got: dict[str, str]) -> bool:
    """Print a precise diff for one case. Return True if any drift."""
    drift = False
    all_files = sorted(set(expected) | set(got))
    for rel in all_files:
        exp = expected.get(rel)
        new = got.get(rel)
        if exp is None:
            drift = True
            print(f"\n[{name}] NEW FILE not in baseline: {rel}")
            continue
        if new is None:
            drift = True
            print(f"\n[{name}] MISSING FILE (in baseline, not produced): {rel}")
            continue
        if exp != new:
            drift = True
            print(f"\n[{name}] DRIFT in {rel}:")
            diff = difflib.unified_diff(
                exp.splitlines(),
                new.splitlines(),
                fromfile=f"baseline/{name}/{rel}",
                tofile=f"current/{name}/{rel}",
                lineterm="",
                n=2,
            )
            for line in diff:
                print(f"    {line}")
    return drift


def cmd_list(args: argparse.Namespace) -> int:
    docker_ok = _docker_available() and not args.skip_docker
    print("CLI cases (texsmith ... without --build/--engine):")
    for case in CLI_CASES:
        flag = "  [requires-docker]" if case.requires_docker else ""
        skip = ""
        if case.requires_docker and not docker_ok:
            skip = "  -> WOULD SKIP"
        print(f"  {case.name:18s} {case.directory}/  {' '.join(case.args)}{flag}{skip}")
    print("\nMkDocs cases (mkdocs build, no PDF):")
    for case in MKDOCS_CASES:
        print(f"  {case.name:18s} {case.directory}/ -> {case.output_subdir}/")
    print(f"\nDocker available: {_docker_available()}")
    print(f"Baseline root: {BASELINE_ROOT}")
    return 0


def _print_summary(action: str, results: Iterable[CaptureResult]) -> None:
    results = list(results)
    captured = [r for r in results if r.status == "captured"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]
    print(f"\n=== {action} summary ===")
    print(f"  captured: {len(captured)}")
    print(f"  skipped : {len(skipped)}")
    print(f"  failed  : {len(failed)}")
    for r in skipped:
        print(f"    - SKIP {r.name}: {r.reason}")
    for r in failed:
        head = r.reason.splitlines()[-1] if r.reason else "(no detail)"
        print(f"    - FAIL {r.name}: {head}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snapshot.py",
        description="Golden harness: capture/diff normalised .tex for TeXSmith examples.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--only",
        nargs="+",
        metavar="CASE",
        help="Restrict to these case names (or example directories).",
    )
    common.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip cases marked requires-docker even if Docker is available.",
    )

    p_cap = sub.add_parser("capture", parents=[common], help="Write the baseline.")
    p_cap.set_defaults(func=cmd_capture)

    p_diff = sub.add_parser("diff", parents=[common], help="Compare to the baseline.")
    p_diff.set_defaults(func=cmd_diff)

    p_list = sub.add_parser("list", parents=[common], help="List known cases.")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
