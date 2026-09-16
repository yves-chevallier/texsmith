"""Publish a built documentation site to the versioned ``gh-pages`` branch.

This is what ``mike deploy --update-aliases <version> <alias>`` followed by
``mike set-default <alias>`` used to do, minus the one thing that made ``mike``
unusable here: ``mike deploy`` loads ``mkdocs.yml`` and *builds the site
itself* with MkDocs, so a site built by Zensical has no way in. This script
takes the built directory instead and writes the same branch layout:

``<version>/``
    the site, verbatim.
``<alias>/``
    one redirect page per HTML page of the version — ``mike``'s
    ``alias_type: redirect``, the shape ``mkdocs.yml`` asks for.
``versions.json``
    ``mike``'s schema, newest version first, the alias moved off whichever
    version held it.
``index.html``
    the redirect to the alias that ``mike set-default`` writes.
``.nojekyll``
    kept, so GitHub Pages serves the ``_``-prefixed asset directories.

Usage::

    uv run python scripts/publish_docs.py 0.8.0 --alias latest [--push]

The site defaults to ``site/`` and the branch checkout to a git worktree the
script creates from ``origin/gh-pages`` under ``build/gh-pages``. Pushing is
opt-in: locally the run stops at the commit, which is there to inspect, and
CI adds ``--push``.

Standard library only: it runs from a docs-only environment.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass, field
import json
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
from typing import Any


VERSIONS_FILE = "versions.json"

REDIRECT_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Redirecting</title>
  <noscript>
    <meta http-equiv="refresh" content="1; url={href}" />
  </noscript>
  <script>
    window.location.replace(
      "{href}" + window.location.search + window.location.hash
    );
  </script>
</head>
<body>
  Redirecting to <a href="{href}">{href}</a>...
</body>
</html>
"""


class PublishError(RuntimeError):
    """A failure the caller reports as a message, not as a traceback."""


def git(*args: str, cwd: Path, capture: bool = True) -> str:
    """Run ``git`` in ``cwd`` and return its stdout."""

    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=capture,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise PublishError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout if capture else ""


def _version_key(version: str) -> tuple[int, tuple[str, ...]]:
    """Order versions the way ``mike`` does, newest first once reversed.

    ``mike`` sorts with ``verspec``'s loose version, which is PyPI's legacy
    comparison key: each run of digits is zero-padded so it compares
    numerically, each run of letters is prefixed so a pre-release sorts below
    the release it precedes, and a version not starting with a digit counts as
    a development version, i.e. newer than every release.
    """

    parts: list[str] = []
    for chunk in re.split(r"(\d+|[a-z]+|\.|-)", version.lower()):
        chunk = {"pre": "c", "preview": "c", "-": "final-", "rc": "c", "dev": "@"}.get(chunk, chunk)
        if not chunk or chunk == ".":
            continue
        if chunk[:1].isdigit():
            parts.append(chunk.zfill(8))
            continue
        if chunk < "*final":
            while parts and parts[-1] == "*final-":
                parts.pop()
            while parts and parts[-1] == "00000000":
                parts.pop()
        parts.append("*" + chunk)
    parts.append("*final")
    return (0 if re.match(r"v?\d", version) else 1, tuple(parts))


@dataclass
class VersionInfo:
    """One entry of ``versions.json``."""

    version: str
    title: str
    aliases: list[str] = field(default_factory=list)
    properties: Any = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VersionInfo:
        return cls(
            version=str(data["version"]),
            title=str(data.get("title") or data["version"]),
            aliases=list(data.get("aliases") or []),
            properties=data.get("properties"),
        )

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": self.version,
            "title": self.title,
            "aliases": list(self.aliases),
        }
        if self.properties:
            data["properties"] = self.properties
        return data


class Versions:
    """``versions.json``, with ``mike``'s ordering and alias bookkeeping."""

    def __init__(self, entries: list[VersionInfo] | None = None) -> None:
        self._entries = {entry.version: entry for entry in entries or []}

    @classmethod
    def loads(cls, text: str) -> Versions:
        return cls([VersionInfo.from_json(item) for item in json.loads(text)])

    def dumps(self) -> str:
        return json.dumps([entry.to_json() for entry in self], indent=2) + "\n"

    def __iter__(self) -> Iterator[VersionInfo]:
        return iter(
            sorted(
                self._entries.values(),
                key=lambda entry: _version_key(entry.version),
                reverse=True,
            )
        )

    def add(self, version: str, title: str, aliases: list[str]) -> VersionInfo:
        """Record ``version`` and move ``aliases`` onto it (``--update-aliases``)."""

        for alias in aliases:
            if alias in self._entries:
                raise PublishError(f"alias {alias!r} is already a version of its own")
            for entry in self._entries.values():
                if entry.version != version and alias in entry.aliases:
                    entry.aliases.remove(alias)

        entry = self._entries.get(version)
        if entry is None:
            entry = VersionInfo(version=version, title=title)
            self._entries[version] = entry
        else:
            entry.title = title
        for alias in aliases:
            if alias not in entry.aliases:
                entry.aliases.append(alias)
        return entry


def walk_files(root: Path) -> Iterator[Path]:
    """Yield every regular file under ``root``, as a path relative to it."""

    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path.relative_to(root)


def redirect_href(source: str, target: str, directory_urls: bool) -> str:
    """The URL a redirect page at ``source`` uses to reach ``target``.

    Both paths are relative to the branch root, and the result is what
    ``mike``'s own redirect pages carry: the relative path, shortened to its
    directory when the site serves pages as directories.
    """

    href = posixpath.relpath(target, posixpath.dirname(source))
    if directory_urls and posixpath.basename(href) == "index.html":
        href = posixpath.dirname(href) + "/"
    return href


def write_alias(root: Path, version: str, alias: str, directory_urls: bool) -> int:
    """Fill ``alias/`` with one redirect page per HTML page of ``version/``."""

    count = 0
    for relative in walk_files(root / version):
        if relative.suffix != ".html":
            continue
        page = relative.as_posix()
        destination = root / alias / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        href = redirect_href(f"{alias}/{page}", f"{version}/{page}", directory_urls)
        destination.write_text(REDIRECT_TEMPLATE.format(href=href), encoding="utf-8")
        count += 1
    return count


def prepare_worktree(repo: Path, worktree: Path, branch: str, remote: str, fetch: bool) -> Path:
    """Check ``branch`` out at ``worktree``, starting from the remote's copy."""

    if worktree.exists():
        if (worktree / ".git").exists():
            return worktree
        raise PublishError(f"{worktree} exists and is not a git checkout")

    if fetch:
        git("fetch", remote, branch, cwd=repo)

    start = f"{remote}/{branch}"
    try:
        git("rev-parse", "--verify", f"{start}^{{commit}}", cwd=repo)
    except PublishError as error:
        raise PublishError(
            f"{start} does not exist; create the branch before publishing"
        ) from error

    worktree.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-B", branch, str(worktree), start, cwd=repo)
    return worktree


def replace_directory(destination: Path, source: Path) -> None:
    """Make ``destination`` an exact copy of ``source``."""

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=False)


def publish(args: argparse.Namespace) -> int:
    repo = Path(git("rev-parse", "--show-toplevel", cwd=Path(args.repo).resolve()).strip())
    site = Path(args.site).resolve()
    if not (site / "index.html").is_file():
        raise PublishError(f"{site} does not look like a built site (no index.html)")

    worktree = prepare_worktree(
        repo,
        Path(args.worktree) if Path(args.worktree).is_absolute() else repo / args.worktree,
        args.branch,
        args.remote,
        fetch=not args.no_fetch,
    )

    aliases = [args.alias] if args.alias else []
    version = args.version
    if version in aliases:
        raise PublishError("the version and its alias cannot have the same name")

    versions_path = worktree / VERSIONS_FILE
    versions = (
        Versions.loads(versions_path.read_text(encoding="utf-8"))
        if versions_path.is_file()
        else Versions()
    )
    versions.add(version, args.title or version, aliases)

    replace_directory(worktree / version, site)
    print(f"{version}/: {sum(1 for _ in walk_files(worktree / version))} files")
    for alias in aliases:
        alias_root = worktree / alias
        if alias_root.exists():
            shutil.rmtree(alias_root)
        pages = write_alias(worktree, version, alias, not args.no_directory_urls)
        print(f"{alias}/: {pages} redirect pages")

    versions_path.write_text(versions.dumps(), encoding="utf-8")
    (worktree / ".nojekyll").touch()
    if aliases:
        (worktree / "index.html").write_text(
            REDIRECT_TEMPLATE.format(href=f"{aliases[0]}/"), encoding="utf-8"
        )

    print(f"{VERSIONS_FILE}: {', '.join(entry.version for entry in versions)}")

    git("add", "--all", cwd=worktree)
    if not git("status", "--porcelain", cwd=worktree).strip():
        print("nothing to commit; the branch already holds this site")
        return 0

    message = args.message or (
        f"Deployed {git('rev-parse', '--short', 'HEAD', cwd=repo).strip()} "
        f"to {version} with Zensical"
    )
    git("commit", "-m", message, cwd=worktree)
    print(f"committed on {args.branch}: {message}")

    if args.push:
        git("push", args.remote, f"HEAD:{args.branch}", cwd=worktree)
        print(f"pushed to {args.remote}/{args.branch}")
    else:
        print(f"not pushed; the commit is in {worktree}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the version to publish, e.g. 0.8.0")
    parser.add_argument(
        "--alias",
        default="latest",
        help="the alias redirecting to this version (default: latest; '' for none)",
    )
    parser.add_argument("--title", default=None, help="the title shown in the selector")
    parser.add_argument("--site", default="site", help="the built site (default: site)")
    parser.add_argument("--repo", default=".", help="the repository to publish from")
    parser.add_argument("--branch", default="gh-pages", help="the branch to publish to")
    parser.add_argument("--remote", default="origin", help="the remote holding it")
    parser.add_argument(
        "--worktree",
        default="build/gh-pages",
        help="the branch checkout, created as a worktree when absent",
    )
    parser.add_argument(
        "--no-fetch", action="store_true", help="trust the local copy of the branch"
    )
    parser.add_argument(
        "--no-directory-urls",
        action="store_true",
        help="the site uses page URLs ending in .html rather than directories",
    )
    parser.add_argument("--message", default=None, help="the commit message")
    parser.add_argument("--push", action="store_true", help="push the commit")
    args = parser.parse_args(argv)

    try:
        return publish(args)
    except PublishError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
