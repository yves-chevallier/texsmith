"""Script-aware helpers for wrapping LaTeX moving arguments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import re
import unicodedata

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.context import RenderContext
from texsmith.fonts.cache import FontCache
from texsmith.fonts.fallback import (
    FallbackBuilder,
    FallbackEntry,
    FallbackLookup,
    FallbackPlan,
    FallbackRepository,
    merge_fallback_summaries,
)
from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.pipeline import generate_noto_metadata, generate_ucharclasses_data


_SKIP_GROUPS = {"latin", "common", "punctuation", "other"}

# Prefer native math macros for single-letter Greek/hebrew math symbols to avoid
# relying on \textgreek wrappers when a math glyph already exists.
_MATH_LETTER_MAP = {
    "\N{GREEK SMALL LETTER ALPHA}": r"\alpha",
    "\N{GREEK SMALL LETTER BETA}": r"\beta",
    "\N{GREEK SMALL LETTER GAMMA}": r"\gamma",
    "\N{GREEK SMALL LETTER DELTA}": r"\delta",
    "\N{GREEK SMALL LETTER EPSILON}": r"\epsilon",
    "\N{GREEK SMALL LETTER ZETA}": r"\zeta",
    "\N{GREEK SMALL LETTER ETA}": r"\eta",
    "\N{GREEK SMALL LETTER THETA}": r"\theta",
    "\N{GREEK SMALL LETTER IOTA}": r"\iota",
    "\N{GREEK SMALL LETTER KAPPA}": r"\kappa",
    "\N{GREEK SMALL LETTER LAMDA}": r"\lambda",
    "\N{GREEK SMALL LETTER MU}": r"\mu",
    "\N{GREEK SMALL LETTER NU}": r"\nu",
    "\N{GREEK SMALL LETTER XI}": r"\xi",
    "\N{GREEK SMALL LETTER PI}": r"\pi",
    "\N{GREEK SMALL LETTER RHO}": r"\rho",
    "\N{GREEK SMALL LETTER SIGMA}": r"\sigma",
    "\N{GREEK SMALL LETTER FINAL SIGMA}": r"\varsigma",
    "\N{GREEK SMALL LETTER TAU}": r"\tau",
    "\N{GREEK SMALL LETTER UPSILON}": r"\upsilon",
    "\N{GREEK SMALL LETTER PHI}": r"\phi",
    "\N{GREEK SMALL LETTER CHI}": r"\chi",
    "\N{GREEK SMALL LETTER PSI}": r"\psi",
    "\N{GREEK SMALL LETTER OMEGA}": r"\omega",
    "\N{GREEK THETA SYMBOL}": r"\vartheta",
    "\N{GREEK PHI SYMBOL}": r"\varphi",
    "\N{GREEK PI SYMBOL}": r"\varpi",
    "\N{GREEK RHO SYMBOL}": r"\varrho",
    "\N{GREEK KAPPA SYMBOL}": r"\varkappa",
    "\N{GREEK LUNATE EPSILON SYMBOL}": r"\varepsilon",
    "\N{GREEK CAPITAL LETTER GAMMA}": r"\Gamma",
    "\N{GREEK CAPITAL LETTER DELTA}": r"\Delta",
    "\N{GREEK CAPITAL LETTER THETA}": r"\Theta",
    "\N{GREEK CAPITAL LETTER LAMDA}": r"\Lambda",
    "\N{GREEK CAPITAL LETTER XI}": r"\Xi",
    "\N{GREEK CAPITAL LETTER PI}": r"\Pi",
    "\N{GREEK CAPITAL LETTER SIGMA}": r"\Sigma",
    "\N{GREEK CAPITAL LETTER UPSILON}": r"\Upsilon",
    "\N{GREEK CAPITAL LETTER PHI}": r"\Phi",
    "\N{GREEK CAPITAL LETTER PSI}": r"\Psi",
    "\N{GREEK CAPITAL LETTER OMEGA}": r"\Omega",
    "\N{ALEF SYMBOL}": r"\aleph",
    "\N{BET SYMBOL}": r"\beth",
    "\N{GIMEL SYMBOL}": r"\gimel",
    "\N{DALET SYMBOL}": r"\daleth",
}
_MATH_LETTER_GROUPS = {"greek", "symbols", "hebrew"}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", value)
    if not slug:
        return "script"
    if slug[0].isdigit():
        slug = f"s{slug}"
    return slug.lower()


def _math_letter_override(chunk: str, group: str | None) -> str | None:
    """Return a math-mode macro for lone Greek/Hebrew symbols when available."""
    if not chunk:
        return None
    normalized_group = group.lower() if isinstance(group, str) else None
    if normalized_group and normalized_group not in _MATH_LETTER_GROUPS:
        return None
    trimmed = chunk.strip()
    if len(trimmed) != 1:
        return None
    command = _MATH_LETTER_MAP.get(trimmed)
    if command is None:
        return None
    prefix_len = len(chunk) - len(chunk.lstrip())
    suffix_len = len(chunk) - len(chunk.rstrip())
    prefix = chunk[:prefix_len]
    suffix = chunk[len(chunk) - suffix_len :] if suffix_len else ""
    return f"{prefix}${command}${suffix}"


@dataclass(slots=True)
class ScriptSpec:
    group: str
    slug: str
    font_name: str | None
    font_command: str
    text_command: str
    count: int = 0

    def to_mapping(self) -> dict[str, str | None]:
        return {
            "group": self.group,
            "slug": self.slug,
            "font_name": self.font_name,
            "font_command": self.font_command,
            "text_command": self.text_command,
            "count": self.count,
        }


class ScriptDetector:
    """Detect script runs and wrap them with dedicated LaTeX macros."""

    def __init__(
        self,
        *,
        cache: FontCache | None = None,
        logger: FontPipelineLogger | None = None,
        skip_groups: Iterable[str] | None = None,
    ) -> None:
        self.cache = cache or FontCache()
        self.logger = logger or FontPipelineLogger()
        self.skip_groups = {entry.lower() for entry in (skip_groups or _SKIP_GROUPS)}
        self._lookup: FallbackLookup | None = None
        self._specs: dict[str, ScriptSpec] = {}

    def _ensure_lookup(self) -> FallbackLookup:
        if self._lookup is None:
            repository = FallbackRepository(cache=self.cache, logger=self.logger)
            had_cache = repository.cache_path.exists()
            classes = generate_ucharclasses_data(cache=self.cache, logger=self.logger)
            coverage = generate_noto_metadata(cache=self.cache, logger=self.logger)
            announce = not had_cache
            entries = FallbackBuilder(logger=self.logger).build(
                classes, coverage, announce=announce
            )
            signature = repository._signature(entries)  # noqa: SLF001
            cached = repository.load(expected_signature=signature)
            if cached is None:
                cached = repository.load_or_build(entries)
            self._lookup = FallbackLookup(cached)
        return self._lookup

    def _classify_char(self, char: str) -> FallbackEntry | None:
        lookup = self._ensure_lookup()
        candidates = lookup.index.ranges_for_codepoint(ord(char))
        if not candidates:
            return None
        return candidates[0]

    def _group_name(self, entry: FallbackEntry | None) -> str | None:
        if entry is None:
            return None
        group = entry.group or entry.name
        if not group:
            return None
        if group.lower() in self.skip_groups:
            return None
        return group

    def _segment_text(
        self,
        text: str,
        *,
        include_whitespace: bool,
    ) -> list[tuple[str | None, str, FallbackEntry | None]]:
        override_group = self._resolve_cjk_override(text)
        runs: list[tuple[str | None, str, FallbackEntry | None]] = []
        current_group: str | None = None
        current_entry: FallbackEntry | None = None
        buffer: list[str] = []

        for char in text:
            entry = self._classify_char(char)
            group = self._group_name(entry)
            if (
                override_group
                and group
                and group.lower() in {"chinese", "japanese", "korean", "cjk"}
            ):
                group = override_group
                entry = entry
            combining = bool(unicodedata.combining(char))
            if current_group is not None and (
                combining or (group and group.lower() == "diacritics")
            ):
                group = current_group
                entry = current_entry
            if include_whitespace and char.isspace() and current_group is not None:
                group = current_group
                entry = current_entry

            if group != current_group and buffer:
                runs.append((current_group, "".join(buffer), current_entry))
                buffer.clear()

            buffer.append(char)
            current_group = group
            current_entry = entry if group else None

        if buffer:
            runs.append((current_group, "".join(buffer), current_entry))

        return runs

    def _resolve_cjk_override(self, text: str) -> str | None:
        try:
            summary = self._ensure_lookup().summary(text)
        except Exception:
            return None

        counts: dict[str, int] = {}
        for entry in summary:
            group = entry.get("group")
            count = entry.get("count")
            if not isinstance(group, str) or not isinstance(count, int):
                continue
            lowered = group.lower()
            if lowered in {"chinese", "japanese", "korean", "cjk"}:
                counts[lowered] = counts.get(lowered, 0) + count

        if not counts:
            return None

        chinese_count = counts.get("chinese", 0) + counts.get("cjk", 0)
        japanese_count = counts.get("japanese", 0)
        korean_count = counts.get("korean", 0)

        if japanese_count and japanese_count >= chinese_count * 0.5:
            return "japanese"
        if korean_count and korean_count >= chinese_count * 0.5:
            return "korean"

        dominant = max(counts.items(), key=lambda item: item[1])[0]
        return dominant

    def _record_spec(self, group: str, entry: FallbackEntry | None) -> ScriptSpec:
        slug = _slugify(group)
        font_name = None
        if entry and entry.font:
            font_name = entry.font.get("name")
        spec = self._specs.get(slug)
        if spec is None:
            spec = ScriptSpec(
                group=group,
                slug=slug,
                font_name=font_name,
                font_command=f"{slug}font",
                text_command=f"text{slug}",
            )
            self._specs[slug] = spec
        elif font_name and not spec.font_name:
            spec.font_name = font_name
        return spec

    def render(
        self,
        text: str,
        *,
        include_whitespace: bool = True,
        legacy_accents: bool = False,
        escape: bool = True,
        wrap_scripts: bool = False,
    ) -> tuple[str, list[dict[str, str | None]]]:
        """Return LaTeX text with script-specific wrappers and usage metadata."""
        if not text:
            return "", []
        segments = self._segment_text(text, include_whitespace=include_whitespace)
        rendered: list[str] = []
        for group, chunk, entry in segments:
            math_override = _math_letter_override(chunk, group)
            if math_override is not None:
                rendered.append(math_override)
                continue
            escaped = escape_latex_chars(chunk, legacy_accents=legacy_accents) if escape else chunk
            if group:
                spec = self._record_spec(group, entry)
                spec.count += len(chunk)
                if wrap_scripts:
                    rendered.append(f"\\{spec.text_command}{{{escaped}}}")
                    continue
            rendered.append(escaped)
        usages = [spec.to_mapping() for spec in self._specs.values()]
        return "".join(rendered), usages


def fallback_summary_to_usage(
    summary: Sequence[Mapping[str, object]],
) -> list[dict[str, str | None]]:
    """Convert a fallback scan summary into script usage records."""
    plan_fonts: dict[str, Mapping[str, object]] = {}
    if isinstance(summary, FallbackPlan):
        plan_fonts = summary.group_fonts or {}
        summary = summary.summary

    usages: list[dict[str, str | None]] = []
    for entry in summary:
        if not isinstance(entry, Mapping):
            continue
        group = entry.get("group") or entry.get("class") or entry.get("name")
        if not isinstance(group, str):
            continue
        group_lower = group.lower()
        if group_lower in _SKIP_GROUPS:
            continue
        slug = _slugify(group)
        font_name = None
        plan_font = plan_fonts.get(group) or plan_fonts.get(group_lower) if plan_fonts else None
        if isinstance(plan_font, Mapping):
            raw_name = plan_font.get("name")
            font_name = str(raw_name) if isinstance(raw_name, str) else None
        if font_name is None:
            font_payload = entry.get("font")
            if isinstance(font_payload, Mapping):
                raw_name = font_payload.get("name")
                font_name = str(raw_name) if isinstance(raw_name, str) else None
        is_emoji = group_lower == "symbols" or (font_name and "emoji" in font_name.lower())
        if is_emoji:
            slug = "emoji"
        count_value = entry.get("count")
        count = int(count_value) if isinstance(count_value, (int, float)) else None
        usages.append(
            {
                "group": group,
                "slug": slug,
                "font_name": font_name,
                "font_command": "texsmithEmojiFont" if slug == "emoji" else f"{slug}font",
                "text_command": "texsmithEmoji" if slug == "emoji" else f"text{slug}",
                "count": count,
            }
        )
    return usages


def merge_script_usage(
    existing: Sequence[Mapping[str, str | None]],
    updates: Sequence[Mapping[str, str | None]],
) -> list[dict[str, str | None]]:
    """Merge script usage lists keyed by slug."""
    merged: dict[str, dict[str, str | None]] = {
        str(entry.get("slug")): dict(entry) for entry in existing if entry.get("slug")
    }
    for entry in updates:
        slug = entry.get("slug")
        if not slug:
            continue
        if slug not in merged:
            merged[slug] = dict(entry)
            continue
        existing_font = merged[slug].get("font_name")
        update_font = entry.get("font_name")
        existing_count = merged[slug].get("count")
        update_count = entry.get("count")

        # Prefer the font coming from the entry with the highest count (when available).
        if update_font:
            if not existing_font:
                merged[slug]["font_name"] = update_font
            else:
                existing_value = (
                    int(existing_count) if isinstance(existing_count, (int, float)) else 0
                )
                update_value = int(update_count) if isinstance(update_count, (int, float)) else 0
                if update_value > existing_value:
                    merged[slug]["font_name"] = update_font

        if isinstance(existing_count, (int, float)) or isinstance(update_count, (int, float)):
            existing_value = int(existing_count) if isinstance(existing_count, (int, float)) else 0
            update_value = int(update_count) if isinstance(update_count, (int, float)) else 0
            merged_count = existing_value + update_value
            merged[slug]["count"] = merged_count if merged_count else None
    return list(merged.values())


def record_script_usage_for_slug(
    slug: str,
    text: str,
    context: RenderContext,
    *,
    detector: ScriptDetector | None = None,
) -> dict[str, str | None]:
    """Record usage/fallback metadata for a known script slug."""
    if detector is None:
        detector_key = "_texsmith_script_detector"
        detector = context.runtime.get(detector_key)
        if not isinstance(detector, ScriptDetector):
            detector = ScriptDetector(cache=FontCache())
            context.runtime[detector_key] = detector

    group = slug
    font_name = None
    try:
        summary = detector._ensure_lookup().summary(text)  # noqa: SLF001
    except Exception:
        summary = []

    if summary:
        dominant = max(summary, key=lambda entry: entry.get("count", 0) or 0)
        candidate_group = dominant.get("group") or dominant.get("class")
        if isinstance(candidate_group, str) and candidate_group.strip():
            group = candidate_group
        font_meta = dominant.get("font")
        if isinstance(font_meta, Mapping):
            raw_name = font_meta.get("name")
            if isinstance(raw_name, str):
                font_name = raw_name

    usage_entry = {
        "group": group,
        "slug": slug,
        "font_name": font_name,
        "font_command": f"{slug}font",
        "text_command": f"text{slug}",
        "count": len(text) if text else None,
    }
    state_usage = getattr(context.state, "script_usage", [])
    context.state.script_usage = merge_script_usage(state_usage, [usage_entry])
    if summary:
        existing = getattr(context.state, "fallback_summary", [])
        context.state.fallback_summary = merge_fallback_summaries(existing, summary)
    return usage_entry


def render_moving_text(
    text: str | None,
    context: RenderContext,
    *,
    include_whitespace: bool = True,
    legacy_accents: bool | None = None,
    escape: bool = True,
    wrap_scripts: bool = False,
) -> str | None:
    """Return LaTeX-safe text with script wrappers and record usage in state."""
    if text is None:
        return None
    detector_key = "_texsmith_script_detector"
    detector = context.runtime.get(detector_key)
    if not isinstance(detector, ScriptDetector):
        detector = ScriptDetector(cache=FontCache())
        context.runtime[detector_key] = detector
    rendered, usage = detector.render(
        text,
        include_whitespace=include_whitespace,
        legacy_accents=bool(legacy_accents)
        if legacy_accents is not None
        else getattr(context.config, "legacy_latex_accents", False),
        escape=escape,
        wrap_scripts=wrap_scripts,
    )
    state_usage = getattr(context.state, "script_usage", [])
    context.state.script_usage = merge_script_usage(state_usage, usage)
    try:
        summary = detector._ensure_lookup().summary(text)  # noqa: SLF001
        existing = getattr(context.state, "fallback_summary", [])
        context.state.fallback_summary = merge_fallback_summaries(existing, summary)
    except Exception:
        pass
    return rendered


def render_script_macros(usages: Iterable[Mapping[str, str | None]]) -> str:
    """Render LaTeX macros declaring script-specific font commands."""
    from texsmith.adapters.latex.formatter import LaTeXFormatter

    scripts = sorted(
        (dict(entry) for entry in usages if entry.get("slug")),
        key=lambda entry: str(entry.get("slug")),
    )
    if not scripts:
        return ""
    formatter = LaTeXFormatter()
    try:
        return formatter.script_macros(scripts=scripts)
    except AttributeError:
        # When the script_macros partial is not available, skip emitting anything.
        return ""
