"""Column layout and environment resolution for YAML tables.

The :func:`compute_layout` entry point consumes a validated :class:`Table` and
produces a :class:`TableLayout` carrying everything the LaTeX renderer needs:
the chosen environment (``tabular`` / ``tabularx`` / ``longtable``), the total
width argument, and the full column preamble string (``colspec``).

All inheritance rules — group-to-leaf propagation of ``align`` / ``width`` /
``width-group`` and width-group resolution — are applied here. Cell-level
overrides (e.g. ``RichCell.align``) are deliberately NOT folded in: they
belong to the row rendering stage because they emit ``\\multicolumn`` on a
per-cell basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal

from .schema import (
    Align,
    Column,
    LeafColumn,
    Table,
    leaf_count,
)


TableEnv = Literal["tabular", "tabularx", "longtable"]

_PERCENT_RE = re.compile(r"^(\d+(?:\.\d+)?)%$")

_ALIGN_WRAPPER: dict[Align, str] = {
    "l": r">{\raggedright\arraybackslash}",
    "r": r">{\raggedleft\arraybackslash}",
    "c": r">{\centering\arraybackslash}",
    "j": "",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnLayout:
    """Per-leaf column description after inheritance and group resolution."""

    name: str
    align: Align
    width_spec: str | None  # resolved LaTeX length, or None when auto-sized
    width_group: str | None


@dataclass(frozen=True)
class TableLayout:
    """Complete layout directive for one table."""

    env: TableEnv
    total_width_spec: str | None
    columns: list[ColumnLayout] = field(default_factory=list)
    colspec: str = ""
    placement: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percent_to_linewidth(value: str) -> str:
    """Convert ``'25%'`` into ``'0.25\\linewidth'`` (100% stays as ``'\\linewidth'``)."""
    match = _PERCENT_RE.match(value)
    if match is None:
        return value
    factor = float(match.group(1)) / 100.0
    if factor == 1.0:
        return r"\linewidth"
    formatted = f"{factor:.4f}".rstrip("0").rstrip(".")
    return rf"{formatted}\linewidth"


def _normalise_width(raw: str | None) -> str | None:
    """Turn a user width spec into a LaTeX length. ``None`` passes through."""
    if raw is None or raw == "auto":
        return None
    return _percent_to_linewidth(raw)


def _scale_percent(raw: str | None, factor: float) -> str | None:
    """Scale a percentage width by ``factor``; non-percent widths pass through."""
    if raw is None:
        return None
    match = _PERCENT_RE.match(raw)
    if match is None:
        return raw
    scaled = float(match.group(1)) * factor
    if scaled <= 0:
        return None
    if abs(scaled - round(scaled)) < 1e-9:
        return f"{round(scaled)}%"
    formatted = f"{scaled:.4f}".rstrip("0").rstrip(".")
    return f"{formatted}%"


# ---------------------------------------------------------------------------
# Leaf flattening with group inheritance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ResolvedLeaf:
    name: str
    align: Align
    width_raw: str | None
    width_group: str | None


def _flatten_with_inheritance(
    col: Column,
    inherited_align: Align | None,
    inherited_width_raw: str | None,
    inherited_group: str | None,
) -> list[_ResolvedLeaf]:
    if isinstance(col, LeafColumn):
        align = col.align or inherited_align or "l"
        width_raw = col.width or inherited_width_raw
        width_group = col.width_group or inherited_group
        return [
            _ResolvedLeaf(
                name=col.name,
                align=align,
                width_raw=width_raw,
                width_group=width_group,
            )
        ]

    # ColumnGroup: pre-divide a declared group width equally across leaves that
    # don't override it. Only leaves missing their own width consume this share.
    total_leaves_in_group = leaf_count(col)
    share_for_children: str | None = None
    if col.width is not None and total_leaves_in_group > 0:
        share_for_children = _scale_percent(col.width, 1.0 / total_leaves_in_group)
        if share_for_children is None:
            # Non-percent width on group: just propagate as-is; LaTeX will split.
            share_for_children = col.width

    child_align = inherited_align if col.align is None else col.align
    child_width_raw = share_for_children if share_for_children is not None else inherited_width_raw
    child_group = inherited_group if col.width_group is None else col.width_group

    leaves: list[_ResolvedLeaf] = []
    for child in col.columns:
        leaves.extend(
            _flatten_with_inheritance(
                child,
                inherited_align=child_align,
                inherited_width_raw=child_width_raw,
                inherited_group=child_group,
            )
        )
    return leaves


def _flatten(columns: list[Column]) -> list[_ResolvedLeaf]:
    leaves: list[_ResolvedLeaf] = []
    for col in columns:
        leaves.extend(
            _flatten_with_inheritance(
                col,
                inherited_align=None,
                inherited_width_raw=None,
                inherited_group=None,
            )
        )
    return leaves


# ---------------------------------------------------------------------------
# Width-group resolution
# ---------------------------------------------------------------------------


def _resolve_width_groups(leaves: list[_ResolvedLeaf]) -> list[_ResolvedLeaf]:
    """Equalise widths of leaves sharing a ``width-group`` identifier.

    For each group, the first leaf carrying an explicit width determines the
    shared width. If all members are auto-sized, the group stays auto (its
    members become ``X`` columns in ``tabularx``).
    """
    group_widths: dict[str, str] = {}
    for leaf in leaves:
        if leaf.width_group is None or leaf.width_raw is None:
            continue
        group_widths.setdefault(leaf.width_group, leaf.width_raw)

    resolved: list[_ResolvedLeaf] = []
    for leaf in leaves:
        if leaf.width_group is not None and leaf.width_group in group_widths:
            resolved.append(
                _ResolvedLeaf(
                    name=leaf.name,
                    align=leaf.align,
                    width_raw=group_widths[leaf.width_group],
                    width_group=leaf.width_group,
                )
            )
        else:
            resolved.append(leaf)
    return resolved


# ---------------------------------------------------------------------------
# Environment selection
# ---------------------------------------------------------------------------


def _total_width_spec(width: str) -> str | None:
    """Translate ``settings.width`` into a LaTeX length, or None for ``auto``."""
    if width == "auto":
        return None
    return _percent_to_linewidth(width)


def _choose_env(table: Table, leaves: list[_ResolvedLeaf], total_width: str | None) -> TableEnv:
    if table.settings.long is True:
        return "longtable"
    has_explicit_x = any(leaf.width_raw == "X" for leaf in leaves)
    if has_explicit_x:
        return "tabularx"
    if total_width is not None and any(leaf.width_raw is None for leaf in leaves):
        return "tabularx"
    return "tabular"


# ---------------------------------------------------------------------------
# Column spec generation
# ---------------------------------------------------------------------------


def _column_spec(leaf: _ResolvedLeaf, env: TableEnv, *, use_x_for_auto: bool) -> str:
    width = _normalise_width(leaf.width_raw)
    wrapper = _ALIGN_WRAPPER[leaf.align]

    # Explicit ``X`` marker: always emit a tabularx ``X`` column regardless
    # of group/auto rules.
    if leaf.width_raw == "X":
        return f"{wrapper}X"

    if width is None:
        if env == "tabularx" and use_x_for_auto:
            return f"{wrapper}X"
        # tabular / longtable, or tabularx with explicit X / width-groups
        # absorbing the remainder: columns without a width keep their natural
        # size (simple alignment letter). ``j`` falls back to ``l`` since
        # justification requires a ``p{}`` column.
        return "l" if leaf.align == "j" else leaf.align

    return f"{wrapper}p{{{width}}}"


def _build_colspec(leaves: list[_ResolvedLeaf], env: TableEnv) -> str:
    # In ``tabularx``, only columns that need to absorb the remaining width
    # should become ``X``. Markers that designate a column as flexible:
    #
    # 1. ``width: X`` — explicit X column.
    # 2. ``width-group: <id>`` — equal-width X columns within the group.
    #
    # When at least one such marker exists, columns without a marker AND
    # without an explicit width keep their natural width (no X). When no
    # marker exists at all, every auto column becomes ``X`` so the table
    # still fills the declared total width — backward-compatible default.
    has_marker = any(leaf.width_group is not None or leaf.width_raw == "X" for leaf in leaves)
    return "".join(
        _column_spec(
            leaf,
            env,
            # When markers exist, only the marked columns expand to X; others
            # without a width keep their natural sizing. When no markers
            # exist, every auto column becomes X (legacy behaviour).
            use_x_for_auto=(not has_marker) or (leaf.width_group is not None),
        )
        for leaf in leaves
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_layout(table: Table) -> TableLayout:
    """Return the resolved :class:`TableLayout` for ``table``.

    The result fully describes the LaTeX environment and column preamble; the
    renderer only needs to emit the body once it has row-level data.
    """
    raw_leaves = _flatten(table.columns)
    leaves = _resolve_width_groups(raw_leaves)
    total_width = _total_width_spec(table.settings.width)
    env = _choose_env(table, leaves, total_width)
    # Tabularx needs an outer width even when the user didn't specify
    # ``table.width``; default to ``\linewidth`` so explicit ``X`` columns
    # have something to absorb.
    if env == "tabularx" and total_width is None:
        total_width = r"\linewidth"
    colspec = _build_colspec(leaves, env)

    column_layouts = [
        ColumnLayout(
            name=leaf.name,
            align=leaf.align,
            width_spec=_normalise_width(leaf.width_raw),
            width_group=leaf.width_group,
        )
        for leaf in leaves
    ]

    # ``tabularx`` without any ``X`` column emits a LaTeX warning; fall back to
    # ``tabular`` (the p{} / natural-width columns already enforce the
    # requested layout).
    if env == "tabularx" and "X" not in colspec:
        env = "tabular"
        colspec = _build_colspec(leaves, env)

    # ``tabular`` does not take a width argument.
    if env == "tabular":
        total_width = None

    return TableLayout(
        env=env,
        total_width_spec=total_width,
        columns=column_layouts,
        colspec=colspec,
        placement=table.settings.placement,
    )


__all__ = [
    "ColumnLayout",
    "TableEnv",
    "TableLayout",
    "compute_layout",
]
