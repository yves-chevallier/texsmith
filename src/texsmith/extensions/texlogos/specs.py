"""Shared specifications for the TeX logo renderer and Markdown extension."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LogoSpec:
    """Describe how to recognise and render a TeX logo token."""

    command: str
    display: str
    description: str
    slug: str
    aliases: tuple[str, ...]

    def match_values(self) -> tuple[str, ...]:
        """Get the strings that should trigger this logo."""

        return self.aliases or (self.display,)


_SPECS: tuple[LogoSpec, ...] = (
    LogoSpec(
        command=r"\TeX{}",
        display="TeX",
        description="Le moteur de base cree par Donald Knuth",
        slug="tex",
        aliases=("TeX",),
    ),
    LogoSpec(
        command=r"\LaTeX{}",
        display="LaTeX",
        description="Le systeme de composition base sur TeX",
        slug="latex",
        aliases=("LaTeX",),
    ),
    LogoSpec(
        command=r"\LaTeXe{}",
        display="LaTeX2\u03b5",
        description="La version moderne de LaTeX",
        slug="latex2e",
        aliases=("LaTeX2e", "LaTeX2\u03b5", "LaTeXe"),
    ),
)


def iter_specs() -> Iterable[LogoSpec]:
    """Iterate over the known logo specifications."""

    return _SPECS


def alias_mapping() -> Mapping[str, LogoSpec]:
    """Build a lookup from alias to spec."""

    mapping: dict[str, LogoSpec] = {}
    for spec in _SPECS:
        for alias in spec.match_values():
            mapping[alias] = spec
    return mapping


__all__ = ["LogoSpec", "alias_mapping", "iter_specs"]
