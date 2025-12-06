"""Build a coverage dataset for Noto fonts."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from texsmith.fonts.cache import FontCache
from texsmith.fonts.logging import FontPipelineLogger


GOOGLE_FONTS_METADATA_URL = "https://fonts.google.com/metadata/fonts"
NOTOFONTS_STATE_URL = (
    "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/state.json"
)
GOOGLE_FONTS_CSS = "https://fonts.googleapis.com/css2?family={}&display=swap"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as response:
        return response.read().decode("utf-8")


@dataclass(slots=True)
class NotoCoverage:
    family: str
    ranges: tuple[tuple[int, int], ...]
    file_base: str
    dir_base: str
    styles: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: dict) -> NotoCoverage:
        return cls(
            family=data["family"],
            ranges=tuple((int(r[0]), int(r[1])) for r in data.get("ranges", [])),
            file_base=data.get("file_base") or "".join(ch for ch in data["family"] if ch.isalnum()),
            dir_base=data.get("dir_base")
            or data.get("file_base")
            or "".join(ch for ch in data["family"] if ch.isalnum()),
            styles=tuple(data.get("otf_styles", []) or ()),
        )

    def to_mapping(self) -> dict:
        return {
            "family": self.family,
            "ranges": [list(r) for r in self.ranges],
            "file_base": self.file_base,
            "dir_base": self.dir_base,
            "otf_styles": list(self.styles),
        }


class NotoCoverageBuilder:
    """Rebuild the Noto coverage dataset or reuse a cached copy."""

    def __init__(
        self,
        *,
        cache: FontCache | None = None,
        logger: FontPipelineLogger | None = None,
        seed_paths: list[Path] | None = None,
    ) -> None:
        self.cache = cache or FontCache()
        self.logger = logger or FontPipelineLogger()
        self.seed_paths = seed_paths or []

    @property
    def cache_path(self) -> Path:
        return self.cache.path("noto_coverage_db.json")

    def _candidate_paths(self) -> list[Path]:
        candidates = [self.cache_path]
        repo_root = Path(__file__).resolve().parents[3]
        candidates.append(repo_root / "sandbox" / "noto_coverage_db.json")
        candidates.append(repo_root / "noto_coverage_db.json")
        candidates.extend(self.seed_paths)
        return candidates

    def load_cached(self) -> tuple[list[NotoCoverage], Path] | None:
        for candidate in self._candidate_paths():
            if not candidate.exists():
                continue
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            data = [NotoCoverage.from_mapping(entry) for entry in raw]
            return data, candidate
        return None

    def _fetch_family_list(self) -> list[str]:
        self.logger.info(
            "Récupération de la liste complète des familles Noto depuis Google Fonts..."
        )
        raw = _http_get(GOOGLE_FONTS_METADATA_URL)
        if raw.startswith(")]}'"):
            raw = raw.split("\n", 1)[1]
        payload = json.loads(raw)
        families = [
            entry["family"]
            for entry in payload.get("familyMetadataList", [])
            if entry["family"].startswith("Noto ")
        ]
        families.sort()
        self.logger.notice(f"{len(families)} familles détectées.")
        return families

    def _normalize_style(self, style: str) -> str | None:
        cleaned = re.sub(r"[^a-z]", "", style.lower())
        mapping = {
            "regular": "regular",
            "italic": "italic",
            "bold": "bold",
            "bolditalic": "bolditalic",
        }
        return mapping.get(cleaned)

    def _fetch_otf_styles(self) -> dict[str, dict]:
        try:
            state = json.loads(_http_get(NOTOFONTS_STATE_URL))
        except Exception as exc:
            self.logger.warning(
                "Impossible de récupérer les styles OTF (%s); poursuite sans styles).", exc
            )
            return {}

        index: dict[str, dict] = {}
        for entry in state.values():
            if not isinstance(entry, dict):
                continue
            for family, meta in entry.get("families", {}).items():
                styles: set[str] = set()
                file_base = None
                dir_base = None
                for path in meta.get("files", []):
                    if "/otf/" not in path:
                        continue
                    filename = path.split("/")[-1]
                    if not filename.lower().endswith(".otf"):
                        continue
                    dir_base = path.split("/")[1] if len(path.split("/")) > 1 else None
                    base_part, sep, style_part = filename.rpartition("-")
                    if not sep:
                        continue
                    style_name = style_part.rsplit(".", 1)[0]
                    normalized = self._normalize_style(style_name)
                    if normalized:
                        styles.add(normalized)
                    if not file_base:
                        file_base = base_part
                family_key = "".join(ch for ch in family if ch.isalnum())
                if styles:
                    index[family] = {
                        "styles": sorted(styles),
                        "file_base": file_base or family_key,
                        "dir_base": dir_base or family_key,
                    }
                    index[family_key] = index[family]
        return index

    def _fetch_ranges(self, family: str) -> list[tuple[int, int]] | None:
        safe_name = urllib.parse.quote(family)
        url = GOOGLE_FONTS_CSS.format(safe_name)
        try:
            css = _http_get(url)
        except Exception:
            return None
        matches = re.findall(r"unicode-range:\s*([^;]+);", css)
        ranges: list[tuple[int, int]] = []
        for match in matches:
            parts = match.replace("unicode-range:", "").strip().split(",")
            for part in parts:
                part = part.strip().replace("U+", "")
                if "-" in part:
                    start_str, end_str = part.split("-", 1)
                    ranges.append((int(start_str, 16), int(end_str, 16)))
                elif part and "?" not in part:
                    val = int(part, 16)
                    ranges.append((val, val))
        return ranges or None

    def build(self) -> list[NotoCoverage]:
        cached = self.load_cached()
        if cached:
            data, source = cached
            self.logger.notice("Base de couverture Noto chargée depuis %s", source)
            if source != self.cache_path:
                with contextlib.suppress(Exception):
                    self.cache_path.write_text(
                        json.dumps([entry.to_mapping() for entry in data], separators=(",", ":")),
                        encoding="utf-8",
                    )
            return data

        families = self._fetch_family_list()
        styles_index = self._fetch_otf_styles()
        dataset: list[NotoCoverage] = []
        with self.logger.progress("Scan des familles Noto", total=len(families)) as advance:
            for family in families:
                ranges = self._fetch_ranges(family)
                advance()
                if not ranges:
                    continue
                key = "".join(ch for ch in family if ch.isalnum())
                styles_meta = styles_index.get(family) or styles_index.get(key) or {}
                dataset.append(
                    NotoCoverage(
                        family=family,
                        ranges=tuple(ranges),
                        file_base=styles_meta.get("file_base", key),
                        dir_base=styles_meta.get("dir_base", key),
                        styles=tuple(styles_meta.get("styles", [])),
                    )
                )
        data = [entry.to_mapping() for entry in dataset]
        try:
            self.cache_path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            self.logger.info("Cache écrit dans %s", self.cache_path)
        except Exception:
            self.logger.warning("Impossible d'écrire le cache de couverture Noto.")
        return dataset


__all__ = [
    "GOOGLE_FONTS_METADATA_URL",
    "NOTOFONTS_STATE_URL",
    "NotoCoverage",
    "NotoCoverageBuilder",
]
