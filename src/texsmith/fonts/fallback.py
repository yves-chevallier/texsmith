"""Higher-level helpers to expose the Noto coverage index as an API."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from texsmith.fonts.analyzer import collate_character_set
from texsmith.fonts.locator import FontLocator
from texsmith.fonts.matcher import FontMatchResult, match_text
from texsmith.fonts.utils import unicode_class_ranges


@dataclass(frozen=True, slots=True)
class UnicodeClassSpec:
    """Describe a font family and the Unicode ranges it should cover."""

    family: str
    ranges: tuple[tuple[str, str], ...]
    missing: bool = False


class NotoFallback:
    """Expose the bundled Noto coverage index as a reusable matcher."""

    def __init__(
        self,
        *,
        fonts_yaml: Path | None = None,
        font_locator: FontLocator | None = None,
    ) -> None:
        self.fonts_yaml = fonts_yaml
        self.font_locator = font_locator or FontLocator(fonts_yaml=fonts_yaml)

    def match_text(self, text: str, *, check_system: bool = True) -> FontMatchResult:
        """Return coverage details for the provided text payload."""
        return match_text(
            text,
            fonts_yaml=self.fonts_yaml,
            check_system=check_system,
            font_locator=self.font_locator,
        )

    def match_payloads(self, *payloads: Any, check_system: bool = True) -> FontMatchResult:
        """Inspect nested payloads and return the matching font coverage."""
        characters = collate_character_set(*payloads)
        return self.match_text(characters, check_system=check_system)

    def unicode_class_specs(
        self,
        text: str | Iterable[str],
        *,
        check_system: bool = True,
    ) -> list[UnicodeClassSpec]:
        """
        Build unicode class specs suitable for ucharclasses from text payloads.

        Missing fonts are still reported so the caller can attempt a copy or
        warn the user.
        """
        characters = "".join(text) if not isinstance(text, str) else text
        match = self.match_text(characters, check_system=check_system)
        specs: list[UnicodeClassSpec] = []
        for family, ranges in match.font_ranges.items():
            if family == "__UNCOVERED__":
                continue
            specs.append(
                UnicodeClassSpec(
                    family=family,
                    ranges=tuple(unicode_class_ranges(ranges)),
                    missing=family in set(match.missing_fonts),
                )
            )
        return specs


__all__ = ["NotoFallback", "UnicodeClassSpec"]
