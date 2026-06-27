"""LaTeX composition for progress-bar nodes, used by the LaTeX writer."""

from __future__ import annotations


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
