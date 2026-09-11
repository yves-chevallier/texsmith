"""Migration loop (plan §4, phases 3–4): copy each example of the parity corpus,
rewrite its sources with ``tmark lint --fix`` and build it with ``--reader tmark``.

Usage: ``uv run python scripts/migrate_examples.py OUT_DIR [ID ...]`` (OUT_DIR under
the repository, e.g. ``build-migr``: the snap ``typst`` binary cannot read ``/tmp``).
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
TMARK = os.environ.get("TMARK", str(ROOT / "vendor/tmark/target/release/tmark"))
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
corpus = yaml.safe_load((ROOT / "tests/parity/corpus.yml").read_text())
only = sys.argv[2:]
rows = []
for e in corpus["examples"]:
    if only and e["id"] not in only:
        continue
    cwd = ROOT / e["cwd"]
    work = OUT / e["id"].replace("@", "_")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(
        cwd, work, ignore=shutil.ignore_patterns("build*", "site", "press", "__pycache__")
    )
    fixes = []
    for md in sorted(work.rglob("*.md")):
        r = subprocess.run([TMARK, "lint", "--fix", str(md)], capture_output=True, text=True)
        fixes.append(
            f"{md.relative_to(work)}:{r.stdout.strip() or r.stderr.strip().splitlines()[-1:]}"
        )
    args = [a for a in e["args"]]
    outdir = work / "out"
    outdir.mkdir()
    cmd = [
        "uv",
        "run",
        "--project",
        str(ROOT),
        "texsmith",
        "--reader",
        "tmark",
        *args,
        "-o",
        str(outdir),
        "--build",
    ]
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=900)
    log = work / "build.log"
    log.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr)
    pdfs = list(outdir.glob("*.pdf"))
    status = "PDF" if pdfs else "FAIL"
    hint = ""
    if status == "FAIL":
        for line in (r.stdout + r.stderr).splitlines():
            if (
                "Undefined control sequence" in line
                or line.startswith("!")
                or "Error" in line
                or "error" in line
            ):
                hint = line.strip()[:110]
                break
    rows.append((e["id"], status, hint))
    print(f"{e['id']:<28} {status:<5} {hint}", flush=True)
ok = sum(1 for r in rows if r[1] == "PDF")
print(f"\n{ok}/{len(rows)} examples build through --reader tmark")
