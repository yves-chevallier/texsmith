from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class ExtraConfig:
    packages: list[tuple[str, str | None]]

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> ExtraConfig:
        return cls(packages=_collect_packages(context))

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_extra_packages"] = self.packages

    def enabled(self) -> bool:
        return bool(self.packages)


class ExtraFragment(BaseFragment[ExtraConfig]):
    name: ClassVar[str] = "ts-extra"
    description: ClassVar[str] = (
        "Auxiliary LaTeX packages loaded on demand (hyperref, ulem, soul, etc.)."
    )
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-extra.jinja.tex"),
            kind="inline",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[ExtraConfig]] = ExtraConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-extra.jinja.tex")
    context_defaults: ClassVar[dict[str, Any]] = {"ts_extra_packages": []}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> ExtraConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: ExtraConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: ExtraConfig) -> bool:
        return config.enabled()


def _collect_packages(context: Mapping[str, object]) -> list[tuple[str, str | None]]:
    combined_strings: list[str] = []
    for value in context.values():
        if isinstance(value, str):
            combined_strings.append(value)
    content = "\n".join(combined_strings)
    packages: list[tuple[str, str | None]] = []

    engine = str(getattr(context, "get", lambda *_: None)("latex_engine") or "").lower()

    def _maybe_add(condition: bool, name: str, options: str | None = None) -> None:
        if condition and (name, options) not in packages:
            packages.append((name, options))

    def _string_option(*keys: str) -> str | None:
        for key in keys:
            value = context.get(key) if hasattr(context, "get") else None
            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed:
                    return trimmed
        return None

    lowered = content.lower()
    _maybe_add("\\nohyphens" in content or "\\nohyphenation" in content, "hyphenat", "htt")
    _maybe_add("\\sout{" in content, "ulem", "normalem")
    if "\\hl{" in content:
        if engine == "lualatex":
            _maybe_add(True, "lua-ul", None)
        elif engine != "xelatex":
            _maybe_add(True, "soul", None)
    _maybe_add("\\progressbar" in content, "progressbar", None)
    _maybe_add(
        "\\enquote{" in content
        or "\\begin{displayquote}" in lowered
        or "\\end{displayquote}" in lowered,
        "csquotes",
        None,
    )
    _maybe_add(
        "\\toprule" in content
        or "\\midrule" in content
        or "\\bottomrule" in content
        or "\\addlinespace" in content,
        "booktabs",
        None,
    )
    _maybe_add("tabularx" in lowered, "ltablex", None)

    math_tokens = (
        "\\begin{equation*}",
        "\\begin{align}",
        "\\begin{align*}",
        "\\begin{alignat}",
        "\\begin{alignat*}",
        "\\begin{xalignat}",
        "\\begin{xalignat*}",
        "\\begin{xxalignat}",
        "\\begin{flalign}",
        "\\begin{flalign*}",
        "\\begin{gather}",
        "\\begin{gather*}",
        "\\begin{multline}",
        "\\begin{multline*}",
        "\\begin{split}",
        "\\begin{aligned}",
        "\\begin{alignedat}",
        "\\begin{gathered}",
        "\\begin{multlined}",
        "\\begin{cases}",
        "\\begin{equation}",
    )
    has_math_env = any(token in content for token in math_tokens)
    has_math_inline = "$$" in content or "$" in content or "\\[" in content or "\\(" in content
    _maybe_add(has_math_env or has_math_inline, "amsmath", None)

    # Pick up float package for strict placement (h/H modifiers).
    float_tokens = (
        "\\begin{figure}[h",
        "\\begin{figure}[h!",
        "\\begin{figure}[H",
        "[h]",
        "[H]",
    )
    _maybe_add(any(token in content for token in float_tokens), "float", None)
    # Always provide float for consistent placement support.
    _maybe_add(True, "float", None)

    link_tokens = ("\\href{", "\\url{", "\\hyperref[", "\\autoref{", "\\nameref{")
    has_links = any(token in content for token in link_tokens)
    disable_hyperref = bool(context.get("ts_extra_disable_hyperref"))
    if not disable_hyperref:
        hyperref_options = _string_option("ts_extra_hyperref_options", "hyperref_options")
        _maybe_add(has_links, "hyperref", hyperref_options)
        _maybe_add(has_links, "bookmark", None)

    _maybe_add("\\begin{longtable}" in lowered, "longtable", None)
    _maybe_add("\\begin{landscape}" in lowered, "pdflscape", None)

    _maybe_add("\\begin{listings}" in lowered or "\\lstset" in lowered, "listings", None)
    _maybe_add("\\begin{minted}" in lowered, "minted", None)
    _maybe_add("\\lstdefinelanguage" in lowered, "listings", None)

    # Always allow long monospace strings to break.
    _maybe_add(True, "seqsplit", None)
    progressbar_options = _string_option("ts_extra_progressbar_options")
    if progressbar_options:
        _maybe_add(True, "progressbar", progressbar_options)

    tikz_option = _string_option("ts_extra_tikz_library")
    if tikz_option:
        _maybe_add(True, "tikz", tikz_option)

    return packages


fragment = ExtraFragment()

__all__ = ["ExtraConfig", "ExtraFragment", "fragment"]
