"""Renderer hooks converting HTML progress bars into LaTeX commands."""

from __future__ import annotations

import re

from bs4 import NavigableString, Tag

from texsmith.adapters.handlers._helpers import coerce_attribute, gather_classes, mark_processed
from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.context import RenderContext
from texsmith.core.rules import RenderPhase, renders


DEFAULT_HEIGHT = "12pt"
THIN_HEIGHT = "6pt"
DEFAULT_OPTIONS = {
    "width": "9cm",
    "heighta": DEFAULT_HEIGHT,
    "roundnessr": "0.1",
    "borderwidth": "1pt",
    "linecolor": "black",
    "filledcolor": "black!60",
    "emptycolor": "black!10",
}


@renders(
    "div",
    phase=RenderPhase.BLOCK,
    priority=58,
    name="texsmith_progressbar",
    nestable=False,
    auto_mark=False,
)
def render_progressbar(element: Tag, context: RenderContext) -> None:
    r"""Convert ``<div class="progress">`` nodes into ``\progressbar`` calls."""
    classes = gather_classes(element.get("class"))
    if "progress" not in classes:
        return

    bar = element.find("div", class_="progress-bar")
    if bar is None:
        return

    percent = _extract_percent(element, bar)
    fraction = max(0.0, min(1.0, percent / 100.0))

    label_node = bar.find("p", class_="progress-label")
    label_text = label_node.get_text(strip=True) if label_node else f"{percent:g}%"
    legacy_accents = getattr(context.config, "legacy_latex_accents", False)
    escaped_label = escape_latex_chars(label_text, legacy_accents=legacy_accents)

    thin = "thin" in classes or "progress-thin" in classes
    latex = _compose_latex(fraction, escaped_label, thin=thin)

    node = mark_processed(NavigableString(latex))
    context.mark_processed(element)
    context.suppress_children(element)
    element.replace_with(node)


def _extract_percent(element: Tag, bar: Tag) -> float:
    for attr in ("data-progress-percent", "data-progress", "data-progress-value"):
        value = coerce_attribute(element.get(attr)) or coerce_attribute(bar.get(attr))
        if value:
            try:
                return float(value)
            except ValueError:
                continue

    style = coerce_attribute(bar.get("style")) or ""
    match = re.search(r"width:\s*([0-9.]+)", style)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    fraction_attr = coerce_attribute(bar.get("data-progress-fraction"))
    if fraction_attr:
        try:
            return float(fraction_attr) * 100.0
        except ValueError:
            return 0.0

    return 0.0


def _compose_latex(fraction: float, label: str, *, thin: bool) -> str:
    value = max(0.0, min(1.0, fraction))
    height = THIN_HEIGHT if thin else DEFAULT_HEIGHT
    options = dict(DEFAULT_OPTIONS)
    options["heighta"] = height
    options_payload = ",".join(f"{key}={value}" for key, value in options.items())
    value_payload = _format_fraction(value)
    return f"{{\\progressbar[{options_payload}]{{{value_payload}}} {label}}}\\par\n"


def _format_fraction(value: float) -> str:
    formatted = f"{value:.4f}"
    trimmed = formatted.rstrip("0").rstrip(".")
    return trimmed or "0"


def register(renderer: object) -> None:
    """Register the progress bar handler with the renderer."""
    register_callable = getattr(renderer, "register", None)
    if not callable(register_callable):
        raise TypeError("Renderer does not expose a 'register' method.")
    if getattr(renderer, "_texsmith_progressbar_registered", False):
        return
    register_callable(render_progressbar)
    renderer._texsmith_progressbar_registered = True  # noqa: SLF001


__all__ = ["register", "render_progressbar"]
