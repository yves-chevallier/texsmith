from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from texsmith.core.fragments import FragmentDefinition, FragmentPiece


def create_fragment() -> FragmentDefinition:
    """Return the auxiliary utilities fragment definition."""
    template_path = Path(__file__).with_name("ts-extra.jinja.tex")
    return FragmentDefinition(
        name="ts-extra",
        pieces=[
            FragmentPiece(
                template_path=template_path,
                kind="inline",
                slot="extra_packages",
            )
        ],
        description="Auxiliary LaTeX packages loaded on demand (hyperref, ulem, soul, etc.).",
        source=template_path,
        context_defaults={"ts_extra_packages": []},
        context_injector=_inject_packages,
        should_render=_has_packages,
    )


def _has_packages(context: Mapping[str, object]) -> bool:
    packages = _collect_packages(context)
    return bool(packages)


def _inject_packages(
    context: dict[str, object], overrides: Mapping[str, object] | None = None
) -> None:
    _ = overrides
    context["ts_extra_packages"] = _collect_packages(context)


def _collect_packages(context: Mapping[str, object]) -> list[tuple[str, str | None]]:
    combined_strings: list[str] = []
    for value in context.values():
        if isinstance(value, str):
            combined_strings.append(value)
    content = "\n".join(combined_strings)
    packages: list[tuple[str, str | None]] = []

    def _maybe_add(condition: bool, name: str, options: str | None = None) -> None:
        if condition:
            packages.append((name, options))

    lowered = content.lower()
    _maybe_add("\\sout{" in content, "ulem", "[normalem]")
    _maybe_add("\\hl{" in content, "soul", None)
    _maybe_add("\\keystroke{" in content or "\\keystrokes{" in content, "keystroke", None)
    _maybe_add("\\progressbar{" in content, "progressbar", None)
    _maybe_add("\\begin{figure}[h" in lowered or "[h]" in lowered, "float", None)

    link_tokens = ("\\href{", "\\url{", "\\hyperref[", "\\autoref{", "\\nameref{")
    has_links = any(token in content for token in link_tokens)
    _maybe_add(has_links, "hyperref", None)
    _maybe_add(has_links, "bookmark", None)

    _maybe_add("\\adjustbox{" in content, "adjustbox", None)

    return packages


__all__ = ["create_fragment"]
