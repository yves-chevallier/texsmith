"""Refresh the tmark fixtures vendored under ``tests/fixtures/tmark-ir/``.

The tmark repository is the single source of truth for the IR schema and the
conformance fixtures; TeXSmith vendors copies so CI runs without a checkout
of tmark (and without the ``tmark`` wheel, which does not exist yet — phase 2
of the migration replaces the vendored schema by ``tmark.schema("ir")``).

Vendored layout::

    tests/fixtures/tmark-ir/ir.json           crates/tmark-ir/schema/ir.json
    tests/fixtures/tmark-ir/VERSION           "<tmark --version> @ <git short sha>"
    tests/fixtures/tmark-ir/conformance/*.md  spec/conformance/*.md (README excluded)
    tests/fixtures/tmark-ir/parsed/*.json     `tmark parse` of each fixture's canonical
                                              block, ids and spans included

Usage::

    uv run python scripts/refresh_tmark_fixtures.py [--tmark-repo ../tmark] \
        [--tmark-bin PATH]

Without a ``tmark`` binary (``--tmark-bin`` or ``<repo>/target/debug/tmark``)
the ``parsed/`` outputs are left untouched. After refreshing, regenerate the
models: ``scripts/gen_ir_models.py --schema tests/fixtures/tmark-ir/ir.json
--version "$(cat tests/fixtures/tmark-ir/VERSION)"``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "tmark-ir"


def fenced_sections(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """``(section title, [(fence language, content)])`` in order, as tmark's runner."""
    out: list[tuple[str, list[tuple[str, str]]]] = []
    fence: tuple[str, list[str], int] | None = None
    for line in text.splitlines():
        if fence is not None:
            lang, content, length = fence
            stripped = line.rstrip()
            if stripped and set(stripped) == {"`"} and len(stripped) >= length:
                if out:
                    out[-1][1].append((lang, "".join(content)))
                fence = None
            else:
                content.append(line + "\n")
            continue
        if line.startswith("## "):
            out.append((line[3:].strip(), []))
        elif line.startswith("```"):
            length = len(line) - len(line.lstrip("`"))
            fence = (line[length:].strip(), [], length)
    return out


def canonical_block(text: str) -> str | None:
    for title, blocks in fenced_sections(text):
        if title == "canonical" and blocks:
            return blocks[0][1]
    return None


def run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def refresh(repo: Path, binary: Path | None) -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo / "crates" / "tmark-ir" / "schema" / "ir.json", FIXTURES / "ir.json")

    conformance = FIXTURES / "conformance"
    conformance.mkdir(exist_ok=True)
    for stale in conformance.glob("*.md"):
        stale.unlink()
    sources = sorted(
        p for p in (repo / "spec" / "conformance").glob("*.md") if p.name != "README.md"
    )
    for source in sources:
        shutil.copyfile(source, conformance / source.name)

    sha = run(["git", "rev-parse", "--short", "HEAD"], cwd=repo).strip()
    version = run([str(binary), "--version"]).split()[-1] if binary else "unknown"
    (FIXTURES / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (FIXTURES / "SOURCE").write_text(
        f"tmark {version}, repository commit {sha}, refreshed by "
        "scripts/refresh_tmark_fixtures.py\n",
        encoding="utf-8",
    )

    if binary is None:
        sys.stderr.write("no tmark binary: parsed/ left untouched\n")
        return 0
    parsed = FIXTURES / "parsed"
    parsed.mkdir(exist_ok=True)
    for stale in parsed.glob("*.json"):
        stale.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        for source in sources:
            block = canonical_block(source.read_text(encoding="utf-8"))
            if block is None:
                continue
            path = Path(tmp) / source.name
            path.write_text(block, encoding="utf-8")
            result = subprocess.run(
                [str(binary), "parse", "--compact", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                sys.stderr.write(f"{source.name}: tmark parse produced no IR, skipped\n")
                continue
            document = json.loads(result.stdout)
            text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
            (parsed / (source.stem + ".json")).write_text(text, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tmark-repo", type=Path, default=ROOT.parent / "tmark")
    parser.add_argument("--tmark-bin", type=Path, help="tmark CLI (default: repo debug build)")
    args = parser.parse_args(argv)
    repo: Path = args.tmark_repo.resolve()
    binary: Path | None = args.tmark_bin
    if binary is None:
        candidate = repo / "target" / "debug" / "tmark"
        binary = candidate if candidate.exists() else None
    return refresh(repo, binary)


if __name__ == "__main__":
    raise SystemExit(main())
