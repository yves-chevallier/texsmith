"""Script-aware helpers for wrapping LaTeX moving arguments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import re

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.context import RenderContext
from texsmith.fonts.cache import FontCache
from texsmith.fonts.fallback import (
    FallbackBuilder,
    FallbackEntry,
    FallbackLookup,
    FallbackRepository,
)
from texsmith.fonts.logging import FontPipelineLogger
from texsmith.fonts.pipeline import generate_noto_metadata, generate_ucharclasses_data


_SKIP_GROUPS = {"latin", "common", "punctuation", "other"}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", value)
    if not slug:
        return "script"
    if slug[0].isdigit():
        slug = f"s{slug}"
    return slug.lower()


@dataclass(slots=True)
class ScriptSpec:
    group: str
    slug: str
    font_name: str | None
    font_command: str
    text_command: str

    def to_mapping(self) -> dict[str, str | None]:
        return {
            "group": self.group,
            "slug": self.slug,
            "font_name": self.font_name,
            "font_command": self.font_command,
            "text_command": self.text_command,
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
            cached = repository.load()
            if cached is None:
                classes = generate_ucharclasses_data(cache=self.cache, logger=self.logger)
                coverage = generate_noto_metadata(cache=self.cache, logger=self.logger)
                entries = FallbackBuilder(logger=self.logger).build(classes, coverage)
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
        runs: list[tuple[str | None, str, FallbackEntry | None]] = []
        current_group: str | None = None
        current_entry: FallbackEntry | None = None
        buffer: list[str] = []

        for char in text:
            entry = self._classify_char(char)
            group = self._group_name(entry)
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
    ) -> tuple[str, list[dict[str, str | None]]]:
        """Return LaTeX text with script-specific wrappers and usage metadata."""
        if not text:
            return "", []
        segments = self._segment_text(text, include_whitespace=include_whitespace)
        rendered: list[str] = []
        for group, chunk, entry in segments:
            escaped = (
                escape_latex_chars(chunk, legacy_accents=legacy_accents) if escape else chunk
            )
            if group:
                spec = self._record_spec(group, entry)
                rendered.append(f"\\{spec.text_command}{{{escaped}}}")
            else:
                rendered.append(escaped)
        usages = [spec.to_mapping() for spec in self._specs.values()]
        return "".join(rendered), usages


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
        if not merged[slug].get("font_name") and entry.get("font_name"):
            merged[slug]["font_name"] = entry.get("font_name")
    return list(merged.values())


def render_moving_text(
    text: str | None,
    context: RenderContext,
    *,
    include_whitespace: bool = True,
    legacy_accents: bool | None = None,
    escape: bool = True,
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
    )
    state_usage = getattr(context.state, "script_usage", [])
    context.state.script_usage = merge_script_usage(state_usage, usage)
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
    return formatter.script_macros(scripts=scripts)
