"""Unicode block helpers and script wrapping utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

import unicodeblocks

from texsmith.fonts.cjk import CJK_BLOCK_OVERRIDES, CJK_SCRIPT_ROWS
from texsmith.fonts.constants import SCRIPT_FALLBACK_ALIASES
from texsmith.fonts.data import noto_dataset
from texsmith.fonts.utils import sanitize_script_id


_CONNECTOR_PUNCTUATION = ",.;:!?\"'()[]{}<>/_-–—…|"
_CONNECTOR_CHAR_CLASS = (
    r"[\s0-9" + re.escape(_CONNECTOR_PUNCTUATION + "\u00A0") + r"]+"
)
NON_LATIN_PATTERN = re.compile(
    r"[^\u0000-\u007F]+(?:" + _CONNECTOR_CHAR_CLASS + r"[^\u0000-\u007F]+)*"
)
CONNECTOR_CHAR_SET = frozenset(
    list("0123456789")
    + list(_CONNECTOR_PUNCTUATION)
    + ["\u00A0", " ", "\t", "\n", "\r", "\v", "\f"]
)
EMOJI_BLOCKS = {
    "Emoticons",
    "Miscellaneous Symbols",
    "Miscellaneous Symbols and Pictographs",
    "Supplemental Symbols and Pictographs",
    "Symbols and Pictographs Extended-A",
    "Symbols for Legacy Computing",
    "Transport and Map Symbols",
}
IGNORED_SCRIPTS = {
    None,
    "",
    "latin",
    "latin-greek-cyrillic",
    "symbols",
}
INLINE_MACROS: dict[str, str] = {}
ENVIRONMENT_MACROS: dict[str, str] = {}
RESERVED_ENVIRONMENTS = {"arabic"}
def _block_key(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch not in {" ", "-", "_"})


def block_override(block_name: str) -> str | None:
    return BLOCK_OVERRIDES.get(_block_key(block_name))


BLOCK_OVERRIDES = {
    _block_key(name): script
    for name, script in (
        ("Greek and Coptic", "greek"),
        ("Greek Extended", "greek"),
        ("Cyrillic", "cyrillic"),
        ("Cyrillic Extended-A", "cyrillic"),
        ("Cyrillic Extended-B", "cyrillic"),
        ("Cyrillic Supplement", "cyrillic"),
        ("Hebrew", "hebrew"),
        ("Arabic", "arabic"),
        ("Arabic Presentation Forms-A", "arabic"),
        ("Arabic Presentation Forms-B", "arabic"),
        ("Arabic Supplement", "arabic"),
        ("Armenian", "armenian"),
        ("Devanagari", "devanagari"),
        ("Bengali", "bengali"),
        ("Gujarati", "gujarati"),
        ("Gurmukhi", "gurmukhi"),
        ("Tamil", "tamil"),
        ("Thai", "thai"),
        ("Lao", "lao"),
        ("Hiragana", "japanese"),
        ("Katakana", "japanese"),
        ("Katakana Phonetic Extensions", "japanese"),
        ("Kana Extended-A", "japanese"),
        ("Kana Extended-B", "japanese"),
        ("Kana Supplement", "japanese"),
        ("Hangul Jamo", "korean"),
        ("Hangul Compatibility Jamo", "korean"),
        ("Hangul Syllables", "korean"),
        ("Hangul Jamo Extended-A", "korean"),
        ("Hangul Jamo Extended-B", "korean"),
        ("Hanifi Rohingya", "hanifi-rohingya"),
    )
}
for block_name, script in CJK_BLOCK_OVERRIDES.items():
    BLOCK_OVERRIDES[_block_key(block_name)] = script

_BLOCK_SCRIPT_MAP: dict[str, str | None] = {}
for display_name, _start, _end, script_id in noto_dataset.UNICODE_BLOCKS:
    if display_name:
        _BLOCK_SCRIPT_MAP[display_name.lower()] = script_id

_FALLBACK_SCRIPT_MACROS: dict[str, str] = {
    row[0]: rf"\TSFallback{sanitize_script_id(row[0])}" for row in noto_dataset.SCRIPT_FALLBACKS
}
_FALLBACK_SCRIPT_MACROS.update(
    {key: rf"\TSFallback{sanitize_script_id(key)}" for key in CJK_SCRIPT_ROWS.keys()}
)
for alias in SCRIPT_FALLBACK_ALIASES:
    _FALLBACK_SCRIPT_MACROS[alias] = rf"\TSFallback{sanitize_script_id(alias)}"


def _normalise_language(script_id: str) -> str:
    return script_id.replace("-", "").replace("_", "")


def _inline_macro(language: str, script_id: str) -> str | None:
    macro = INLINE_MACROS.get(language)
    if macro:
        return macro
    if script_id in _FALLBACK_SCRIPT_MACROS:
        return rf"\text{language}"
    return None


def _wrapped_inline(command: str, segment: str) -> str:
    if command.startswith(r"\TSFallback"):
        return rf"{{{command} {segment}}}"
    return rf"{command}{{{segment}}}"


@dataclass(slots=True)
class ScriptUsage:
    """Aggregated data about a script encountered in the document."""

    script_id: str
    language: str
    strategy: str
    inline_command: str
    environment: str | None
    blocks: set[str] = field(default_factory=set)
    count: int = 0
    samples: list[str] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "script_id": self.script_id,
            "language": self.language,
            "strategy": self.strategy,
            "inline_command": self.inline_command,
            "environment": self.environment,
            "blocks": sorted(self.blocks),
            "count": self.count,
            "samples": list(self.samples),
        }


@dataclass(slots=True)
class ScriptTracker:
    """Track scripts encountered while processing text."""

    usages: dict[str, ScriptUsage] = field(default_factory=dict)

    def record(self, script_id: str, block_name: str, segment: str) -> None:
        language = LANGUAGE_ALIASES.get(script_id, _normalise_language(script_id))
        inline_command = _inline_macro(language, script_id)
        environment = ENVIRONMENT_MACROS.get(language)
        usage = self.usages.get(script_id)
        if usage is None:
            usage = ScriptUsage(
                script_id=script_id,
                language=language,
                strategy="polyglossia",
                inline_command=inline_command,
                environment=environment,
            )
            self.usages[script_id] = usage

        usage.blocks.add(block_name)
        usage.count += len(segment)
        if len(usage.samples) < 5:
            usage.samples.append(segment[:80])

    def to_payload(self) -> list[dict[str, Any]]:
        return [usage.to_payload() for usage in self.usages.values()]

    def has_usage(self) -> bool:
        return bool(self.usages)


LANGUAGE_ALIASES: dict[str, str] = {
    "japanese": "japanese",
    "korean": "korean",
    "chinese": "chinese",
}


def _script_for_block(block_name: str) -> str | None:
    lowered = block_name.lower()
    override = block_override(block_name)
    if override:
        return override
    mapped = _BLOCK_SCRIPT_MAP.get(lowered)
    return mapped


def _should_use_block(segment: str) -> bool:
    if segment.count("\n") >= 1:
        return True
    return len(segment) > 120 and segment.count(" ") > 4


def _wrap_segment(segment: str, script_id: str, language: str, use_block: bool) -> str:
    inline_command = _inline_macro(language, script_id)
    environment = environment_name(language)
    if use_block:
        if environment:
            return (
                f"\\begin{{{environment}}}\n"
                f"{segment}\n"
                f"\\end{{{environment}}}"
            )
        if inline_command:
            return _wrapped_inline(inline_command, segment)
        return segment
    if inline_command:
        return _wrapped_inline(inline_command, segment)
    return segment


def wrap_foreign_scripts(text: str, tracker: ScriptTracker | None = None) -> str:
    """Wrap sequences of non-Latin characters with script-specific macros."""
    if not text or not isinstance(text, str):
        return text

    tracker = tracker or ScriptTracker()
    result: list[str] = []
    last_idx = 0
    for match in NON_LATIN_PATTERN.finditer(text):
        start, end = match.span()
        result.append(text[last_idx:start])
        chunk = match.group(0)
        result.append(_process_chunk(chunk, tracker))
        last_idx = end
    result.append(text[last_idx:])
    return "".join(result)


def _process_chunk(chunk: str, tracker: ScriptTracker) -> str:
    segments: list[str] = []
    current_script: str | None = None
    current_block = ""
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        segment = "".join(buffer)
        buffer.clear()
        if not current_script or current_script in IGNORED_SCRIPTS:
            segments.append(segment)
            return
        tracker.record(current_script, current_block, segment)
        language = LANGUAGE_ALIASES.get(current_script, _normalise_language(current_script))
        use_block = _should_use_block(segment)
        wrapped = _wrap_segment(segment, current_script, language, use_block)
        segments.append(wrapped)

    for char in chunk:
        if char in CONNECTOR_CHAR_SET:
            buffer.append(char)
            continue
        block = unicodeblocks.blockof(char)
        block_name = block.name
        script = None
        if block_name in EMOJI_BLOCKS:
            script = None
        else:
            script = _script_for_block(block_name)
        if script != current_script and buffer:
            flush()
        current_script = script
        current_block = block_name
        buffer.append(char)
    flush()
    return "".join(segments)


def summarise_scripts(usages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a stable list for template contexts."""
    return sorted(usages, key=lambda entry: entry.get("script_id", ""))


__all__ = [
    "ScriptTracker",
    "wrap_foreign_scripts",
    "summarise_scripts",
    "ScriptUsage",
    "block_override",
    "environment_name",
]
def environment_name(language: str) -> str | None:
    override = ENVIRONMENT_MACROS.get(language)
    if override:
        return override
    if language in RESERVED_ENVIRONMENTS:
        return None
    return language
