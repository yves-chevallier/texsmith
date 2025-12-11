"""Tools to fetch and parse ucharclasses definitions from CTAN."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import urllib.request
import zipfile

from texsmith.fonts.cache import FontCache
from texsmith.fonts.logging import FontPipelineLogger


CTAN_UCHARCLASSES_ZIP = "https://mirrors.ctan.org/macros/xetex/latex/ucharclasses.zip"

DO_PATTERN = re.compile(r"""\\do\{([^}]+)\}\{"?([0-9A-Fa-f]+)\}\{"?([0-9A-Fa-f]+)\}""")
GROUP_PATTERN = re.compile(r"""\\def\\([A-Za-z0-9]+)Classes\{""")
DO_NAME_PATTERN = re.compile(r"""\\do\{([^}]+)\}""")


@dataclass(slots=True)
class UCharClass:
    name: str
    start: int
    end: int
    group: str | None = None
    font: dict | None = None

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "start_hex": f"U+{self.start:04X}",
            "end_hex": f"U+{self.end:04X}",
        }
        if self.group:
            payload["group"] = self.group
        if self.font:
            payload["font"] = self.font
        return payload


class UCharClassesBuilder:
    """Download and parse ucharclasses.sty from CTAN."""

    def __init__(
        self,
        *,
        cache: FontCache | None = None,
        logger: FontPipelineLogger | None = None,
        source_url: str = CTAN_UCHARCLASSES_ZIP,
        extra_sources: list[Path] | None = None,
    ) -> None:
        self.cache = cache or FontCache()
        self.logger = logger or FontPipelineLogger()
        self.source_url = source_url
        self.extra_sources = extra_sources or []

    def _cached_sty_path(self) -> Path:
        return self.cache.path("ucharclasses", "ucharclasses.sty")

    def _download_zip(self, target: Path) -> Path:
        self.logger.info("Downloading ucharclasses from %s", self.source_url)
        with urllib.request.urlopen(self.source_url) as response:
            target.write_bytes(response.read())
        return target

    def _extract_sty(self, archive: Path, destination: Path) -> Path:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.filename.lower().endswith("ucharclasses.sty"):
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    return destination
        raise FileNotFoundError("ucharclasses.sty not found in downloaded archive.")

    def _ensure_sty(self) -> Path:
        cached = self._cached_sty_path()
        candidates = [
            cached,
            *self.extra_sources,
        ]
        for candidate in candidates:
            if candidate.exists():
                if candidate != cached:
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(candidate, cached)
                self.logger.debug("ucharclasses.sty loaded from %s", candidate)
                return cached
        with self.cache.tempdir() as tmp:
            archive = tmp / "ucharclasses.zip"
            self._download_zip(archive)
            sty_path = self._extract_sty(archive, cached)
            self.logger.info("ucharclasses.sty extracted to %s", sty_path)
            return sty_path

    def sty_path(self) -> Path:
        """Return the local ucharclasses.sty path, downloading it if needed."""
        return self._ensure_sty()

    @staticmethod
    def _iter_class_ranges(text: str):
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            for match in DO_PATTERN.finditer(line):
                name, start_hex, end_hex = match.groups()
                yield name, int(start_hex, 16), int(end_hex, 16)

    @staticmethod
    def _apply_grouping(raw: str, classes: dict[str, UCharClass]) -> None:
        group_priority = {"Japanese": 3, "Korean": 3, "Chinese": 3, "CJK": 1}
        priorities: dict[str, int] = {}
        current_group = None
        for line in raw.splitlines():
            stripped = line.strip()
            match = GROUP_PATTERN.match(stripped)
            if match:
                current_group = match.group(1)
                continue
            if current_group and stripped.startswith("}"):
                current_group = None
                continue
            if current_group and current_group not in ("All", "Other"):
                priority = group_priority.get(current_group, 2)
                for match in DO_NAME_PATTERN.finditer(stripped):
                    cls_name = match.group(1)
                    if cls_name not in classes:
                        continue
                    previous_priority = priorities.get(cls_name, 0)
                    if previous_priority >= priority:
                        continue
                    classes[cls_name].group = current_group
                    priorities[cls_name] = priority

    def build(self) -> list[UCharClass]:
        """Return parsed ucharclasses definitions, downloading assets if needed."""
        had_cached_sty = self._cached_sty_path().exists()
        sty_path = self._ensure_sty()
        raw = sty_path.read_text(encoding="utf-8")
        seen: dict[str, UCharClass] = {}
        for name, start, end in self._iter_class_ranges(raw):
            seen.setdefault(name, UCharClass(name=name, start=start, end=end))
        self._apply_grouping(raw, seen)
        ordered = sorted(seen.values(), key=lambda c: c.start)
        log_fn = self.logger.info if not had_cached_sty else self.logger.debug
        log_fn(f"{len(ordered)} Unicode classes detected.")
        return ordered

    def export_json(self, target: Path) -> None:
        """Persist classes to JSON; useful for debugging or downstream tools."""
        data = [cls.to_dict() for cls in self.build()]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.logger.info("Writing Unicode classes to %s", target)


__all__ = ["CTAN_UCHARCLASSES_ZIP", "UCharClass", "UCharClassesBuilder"]
