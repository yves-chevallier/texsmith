"""Schema, parser, and structural validator for TeXSmith YAML tables.

Given a raw mapping (as produced by ``yaml.safe_load``) this module returns a
fully validated :class:`Table` instance. All structural invariants — column
shape, row widths, multirow / multicolumn absorption — are checked at
construction time so downstream layers can operate on a trusted tree.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Scalar = str | int | float | bool | None
Align = Literal["l", "c", "r", "j"]

_PERCENT_RE = re.compile(r"^\d+(?:\.\d+)?%$")
_PLACEMENT_RE = re.compile(r"^[hHtbpT!]+$")
_RICH_KEYS = frozenset({"value", "rows", "cols", "align"})

# User-friendly long forms accepted everywhere ``align`` is allowed.
_ALIGN_ALIASES = {
    "l": "l",
    "left": "l",
    "c": "c",
    "center": "c",
    "centre": "c",
    "r": "r",
    "right": "r",
    "j": "j",
    "justify": "j",
    "justified": "j",
}


def _normalise_align(value: Any) -> str | None:
    """Map a user-supplied alignment to its short form, or return None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"align must be a string, got {type(value).__name__}")
    key = value.strip().lower()
    if key in _ALIGN_ALIASES:
        return _ALIGN_ALIASES[key]
    raise ValueError(
        f"invalid align value {value!r}; expected one of {sorted(set(_ALIGN_ALIASES))}"
    )


# ---------------------------------------------------------------------------
# Width helpers
# ---------------------------------------------------------------------------


def _validate_width(raw: Any) -> str:
    """Return a cleaned width specification or raise an error.

    Accepts:
    - ``"auto"``: no fixed width (cell is sized naturally).
    - ``"X"`` (case-insensitive): explicit ``tabularx`` ``X`` column —
      the column absorbs whatever horizontal space is left.
    - ``"NN%"``: percentage of the table width.
    - any other string: passed through as an opaque LaTeX length.
    """
    if not isinstance(raw, str):
        raise TypeError(f"width must be a string, got {type(raw).__name__}")
    value = raw.strip()
    if not value:
        raise ValueError("width must not be empty")
    if value == "auto":
        return value
    if value.lower() == "x":
        return "X"
    if _PERCENT_RE.match(value):
        percent = float(value[:-1])
        if not 0 < percent <= 100:
            raise ValueError(f"width percentage must be in (0, 100], got {value!r}")
        return value
    return value  # opaque LaTeX length


# ---------------------------------------------------------------------------
# Table-level settings
# ---------------------------------------------------------------------------


class TableSettings(BaseModel):
    """Knobs from the ``table:`` section of the YAML payload."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    width: str = "auto"
    placement: str | None = None
    long: bool | Literal["auto"] = "auto"

    @field_validator("width", mode="before")
    @classmethod
    def _check_width(cls, value: Any) -> str:
        return _validate_width(value)

    @field_validator("placement")
    @classmethod
    def _check_placement(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _PLACEMENT_RE.match(value):
            raise ValueError(f"invalid placement spec: {value!r}")
        return value


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


class LeafColumn(BaseModel):
    """Terminal column with optional alignment and width metadata."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    align: Align | None = None
    width: str | None = None
    width_group: str | None = Field(default=None, alias="width-group")

    @field_validator("align", mode="before")
    @classmethod
    def _check_align(cls, value: Any) -> str | None:
        return _normalise_align(value)

    @field_validator("width", mode="before")
    @classmethod
    def _check_width(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _validate_width(value)

    @field_validator("width_group", mode="before")
    @classmethod
    def _coerce_group(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)


class ColumnGroup(BaseModel):
    """Recursive column group containing an ordered list of sub-columns."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    columns: list[Column] = Field(min_length=1)
    align: Align | None = None
    width: str | None = None
    width_group: str | None = Field(default=None, alias="width-group")

    @field_validator("align", mode="before")
    @classmethod
    def _check_align(cls, value: Any) -> str | None:
        return _normalise_align(value)

    @field_validator("width", mode="before")
    @classmethod
    def _check_width(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _validate_width(value)

    @field_validator("width_group", mode="before")
    @classmethod
    def _coerce_group(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)


Column = LeafColumn | ColumnGroup
ColumnGroup.model_rebuild()


def column_leaves(col: Column) -> list[LeafColumn]:
    """Return the terminal columns underneath ``col`` in order."""
    if isinstance(col, LeafColumn):
        return [col]
    leaves: list[LeafColumn] = []
    for child in col.columns:
        leaves.extend(column_leaves(child))
    return leaves


def leaf_count(col: Column) -> int:
    return len(column_leaves(col))


def total_leaves(columns: Iterable[Column]) -> int:
    return sum(leaf_count(c) for c in columns)


def header_depth(col: Column) -> int:
    """Depth of the header hierarchy (1 for a leaf)."""
    if isinstance(col, LeafColumn):
        return 1
    return 1 + max(header_depth(c) for c in col.columns)


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------


class RichCell(BaseModel):
    """Explicit cell carrying span and alignment overrides."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    value: Scalar = None
    rows: int = 1
    cols: int = 1
    align: Align | None = None

    @field_validator("align", mode="before")
    @classmethod
    def _check_align(cls, value: Any) -> str | None:
        return _normalise_align(value)

    @field_validator("rows", "cols")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("rows and cols must be >= 1")
        return value


CellLeafValue = Scalar | RichCell
CellTopValue = Scalar | RichCell | list[CellLeafValue]


def _is_rich_dict(raw: Any) -> bool:
    return isinstance(raw, dict) and "value" in raw and _RICH_KEYS.issuperset(raw.keys())


def _parse_cell_leaf(raw: Any) -> CellLeafValue:
    if raw is None or isinstance(raw, (str, int, float, bool)):
        return raw
    if _is_rich_dict(raw):
        return RichCell(**raw)
    raise ValueError(f"invalid cell value: {raw!r}")


def _parse_cell_top(raw: Any) -> CellTopValue:
    if isinstance(raw, list):
        return [_parse_cell_leaf(item) for item in raw]
    return _parse_cell_leaf(raw)


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


class Separator(BaseModel):
    """Horizontal separator, optionally labelled."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    separator: Literal[True] = True
    label: str | None = None
    double_rule: bool = Field(default=False, alias="double-rule")


class DataRow(BaseModel):
    """Row of data with cells stored in positional top-level-column order."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    label: str
    cells: list[Any] = Field(default_factory=list)
    source: Literal["positional", "named"] = "positional"


Row = Separator | DataRow


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


class Table(BaseModel):
    """Top-level table model. Built via :func:`parse_table`."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    settings: TableSettings = Field(default_factory=TableSettings)
    columns: list[Column] = Field(min_length=2)
    rows: list[Row] = Field(default_factory=list)
    footer: list[Row] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_structure(self) -> Table:
        build_matrix(self)
        return self


# ---------------------------------------------------------------------------
# Column parsing
# ---------------------------------------------------------------------------


def _parse_column(raw: Any) -> Column:
    if isinstance(raw, bool):
        raise ValueError(f"invalid column descriptor: {raw!r}")  # noqa: TRY004
    if isinstance(raw, (str, int, float)):
        return LeafColumn(name=str(raw))
    if isinstance(raw, dict):
        if "columns" in raw:
            payload = dict(raw)
            payload["columns"] = [_parse_column(c) for c in payload["columns"]]
            if "name" not in payload:
                raise ValueError(f"grouped column is missing 'name': {raw!r}")
            payload["name"] = str(payload["name"])
            return ColumnGroup.model_validate(payload)
        if "name" not in raw:
            raise ValueError(f"leaf column is missing 'name': {raw!r}")
        payload = dict(raw)
        payload["name"] = str(payload["name"])
        return LeafColumn.model_validate(payload)
    raise ValueError(f"invalid column descriptor: {raw!r}")


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def _parse_separator(raw: dict[str, Any]) -> Separator:
    sep = raw["separator"]
    if sep is True:
        payload: dict[str, Any] = {"separator": True}
        if "label" in raw:
            payload["label"] = raw["label"]
        if "double-rule" in raw:
            payload["double-rule"] = raw["double-rule"]
        return Separator.model_validate(payload)
    if isinstance(sep, dict):
        extras = [k for k in raw if k != "separator"]
        if extras:
            raise ValueError(
                f"separator carries top-level keys {sorted(extras)} alongside a "
                f"mapping body; move them inside 'separator'."
            )
        payload = {"separator": True, **sep}
        return Separator.model_validate(payload)
    raise ValueError(f"invalid separator payload: {raw!r}")


def _parse_positional_row(raw: list[Any]) -> DataRow:
    if not raw:
        raise ValueError("empty row")
    label, *cells = raw
    if label is None:
        label = ""
    return DataRow(
        label=str(label),
        cells=[_parse_cell_top(c) for c in cells],
        source="positional",
    )


def _parse_named_row(raw: dict[str, Any], columns: list[Column]) -> DataRow:
    if "label" in raw and "cells" in raw:
        label = raw["label"]
        cells_map = raw["cells"]
        extras = set(raw) - {"label", "cells"}
        if extras:
            raise ValueError(f"named row {label!r} has unexpected keys {sorted(extras)}")
    elif len(raw) == 1:
        ((label, cells_map),) = raw.items()
    else:
        raise ValueError(f"invalid named row: {raw!r}")

    if not isinstance(cells_map, dict):
        raise TypeError(f"named row {label!r} must map column names to cell values")

    data_cols = columns[1:]
    known = {col.name for col in data_cols}
    unknown = [key for key in cells_map if key not in known]
    if unknown:
        raise ValueError(
            f"named row {label!r}: unknown column(s) {sorted(unknown)}; "
            f"available columns: {sorted(known)}"
        )

    ordered: list[Any] = []
    for col in data_cols:
        if col.name in cells_map:
            ordered.append(_parse_cell_top(cells_map[col.name]))
        else:
            ordered.append(None)
    return DataRow(label=str(label), cells=ordered, source="named")


def _parse_row(raw: Any, columns: list[Column]) -> Row:
    if isinstance(raw, dict) and "separator" in raw:
        return _parse_separator(raw)
    if isinstance(raw, list):
        return _parse_positional_row(raw)
    if isinstance(raw, dict):
        return _parse_named_row(raw, columns)
    raise ValueError(f"invalid row: {raw!r}")


# ---------------------------------------------------------------------------
# Public parser entry point
# ---------------------------------------------------------------------------


def parse_table(raw: dict[str, Any]) -> Table:
    """Construct a validated :class:`Table` from a raw YAML mapping."""
    if not isinstance(raw, dict):
        raise TypeError("yaml table payload must be a mapping")

    unknown = set(raw) - {"table", "columns", "rows", "footer"}
    if unknown:
        raise ValueError(f"unknown top-level key(s): {sorted(unknown)}")

    if "columns" not in raw:
        raise ValueError("yaml table payload is missing 'columns'")

    columns = [_parse_column(c) for c in raw["columns"]]
    rows = [_parse_row(r, columns) for r in raw.get("rows") or []]
    footer = [_parse_row(r, columns) for r in raw.get("footer") or []]

    settings_raw = raw.get("table") or {}
    if not isinstance(settings_raw, dict):
        raise TypeError("'table' section must be a mapping")
    settings = TableSettings.model_validate(settings_raw)

    return Table(settings=settings, columns=columns, rows=rows, footer=footer)


# ---------------------------------------------------------------------------
# Table-config payload (applied to a plain Markdown table)
# ---------------------------------------------------------------------------


class ColumnConfig(BaseModel):
    """Per-column attributes for a ``yaml table-config`` block.

    Columns are matched positionally against the preceding Markdown table
    (no ``name`` field — there is no header lookup, the markdown header
    stays exactly as written).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    align: Align | None = None
    width: str | None = None
    width_group: str | None = Field(default=None, alias="width-group")

    @field_validator("align", mode="before")
    @classmethod
    def _check_align(cls, value: Any) -> str | None:
        return _normalise_align(value)

    @field_validator("width", mode="before")
    @classmethod
    def _check_width(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _validate_width(value)

    @field_validator("width_group", mode="before")
    @classmethod
    def _coerce_group(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)


class TableConfig(BaseModel):
    """Full payload of a ``yaml table-config`` fence."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    settings: TableSettings = Field(default_factory=TableSettings)
    columns: list[ColumnConfig] = Field(default_factory=list)


def parse_table_config(raw: Any) -> TableConfig:
    """Build a validated :class:`TableConfig` from a raw YAML mapping."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise TypeError("yaml table-config payload must be a mapping")

    unknown = set(raw) - {"table", "columns"}
    if unknown:
        raise ValueError(f"unknown top-level key(s): {sorted(unknown)}")

    settings_raw = raw.get("table") or {}
    if not isinstance(settings_raw, dict):
        raise TypeError("'table' section must be a mapping")
    settings = TableSettings.model_validate(settings_raw)

    columns_raw = raw.get("columns") or []
    if not isinstance(columns_raw, list):
        raise TypeError("'columns' must be a list of column descriptors")
    columns = [ColumnConfig.model_validate(c or {}) for c in columns_raw]

    return TableConfig(settings=settings, columns=columns)


def synthesise_table_for_config(config: TableConfig, n_columns: int) -> Table:
    """Produce a :class:`Table` shell suitable for :func:`compute_layout`.

    Used to drive the existing layout machinery for a table-config payload
    bound to an existing Markdown table whose column count is ``n_columns``.
    Names are synthesised; rows stay empty since validation only requires
    column structure.
    """
    if n_columns < 2:
        raise ValueError(f"table-config requires at least 2 columns, got {n_columns}")
    columns: list[Column] = []
    for i in range(n_columns):
        cfg = config.columns[i] if i < len(config.columns) else ColumnConfig()
        columns.append(
            LeafColumn(
                name=f"col_{i}",
                align=cfg.align,
                width=cfg.width,
                width_group=cfg.width_group,
            )
        )
    return Table(settings=config.settings, columns=columns, rows=[], footer=[])


# ---------------------------------------------------------------------------
# Leaf matrix + span validation
# ---------------------------------------------------------------------------


class LeafCell(BaseModel):
    """Dense cell occupying a single leaf slot in the matrix."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    value: Scalar = None
    absorbed: bool = False
    origin: tuple[int, int] = (0, 0)
    rows: int = 1
    cols: int = 1
    align: Align | None = None


class LeafMatrix(BaseModel):
    """Leaf-level representation of a table's body and footer sections."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    body: list[list[LeafCell]] = Field(default_factory=list)
    footer: list[list[LeafCell]] = Field(default_factory=list)
    body_row_kinds: list[Literal["data", "separator"]] = Field(default_factory=list)
    footer_row_kinds: list[Literal["data", "separator"]] = Field(default_factory=list)
    separators: list[Separator] = Field(default_factory=list)
    footer_separators: list[Separator] = Field(default_factory=list)


# ---- span placement primitives -------------------------------------------


def _set_cell(
    row: list[LeafCell | None],
    pos: int,
    cell: LeafCell,
    *,
    row_label: str,
    section_label: str,
) -> None:
    if row[pos] is not None:
        raise ValueError(f"{section_label} row {row_label!r}: cell collides at leaf column {pos}")
    row[pos] = cell


def _place_scalar(
    value: Scalar,
    row: list[LeafCell | None],
    cursor: int,
    span: int,
    row_idx: int,
    row_label: str,
    section_label: str,
) -> None:
    for offset in range(span):
        pos = cursor + offset
        _set_cell(
            row,
            pos,
            LeafCell(value=value, origin=(row_idx, pos)),
            row_label=row_label,
            section_label=section_label,
        )


def _place_list(
    items: list[CellLeafValue],
    row: list[LeafCell | None],
    cursor: int,
    span: int,
    row_idx: int,
    row_label: str,
    section_label: str,
) -> None:
    if len(items) > span:
        raise ValueError(
            f"{section_label} row {row_label!r}: list of {len(items)} cell(s) "
            f"for a column with only {span} sub-column(s)"
        )
    padded: list[CellLeafValue] = list(items) + [None] * (span - len(items))
    offset = 0
    while offset < span:
        pos = cursor + offset
        item = padded[offset]
        if isinstance(item, RichCell):
            if offset + item.cols > span:
                raise ValueError(
                    f"{section_label} row {row_label!r}: rich cell in list spans "
                    f"{item.cols} leaf column(s), exceeding the group's remaining "
                    f"{span - offset}"
                )
            _set_cell(
                row,
                pos,
                LeafCell(
                    value=item.value,
                    origin=(row_idx, pos),
                    rows=item.rows,
                    cols=item.cols,
                    align=item.align,
                ),
                row_label=row_label,
                section_label=section_label,
            )
            for extra in range(1, item.cols):
                _set_cell(
                    row,
                    cursor + offset + extra,
                    LeafCell(absorbed=True, origin=(row_idx, pos)),
                    row_label=row_label,
                    section_label=section_label,
                )
            offset += item.cols
            continue
        _set_cell(
            row,
            pos,
            LeafCell(value=item, origin=(row_idx, pos)),
            row_label=row_label,
            section_label=section_label,
        )
        offset += 1


def _place_rich(
    cell: RichCell,
    row: list[LeafCell | None],
    cursor: int,
    row_idx: int,
    total: int,
    row_label: str,
    section_label: str,
) -> None:
    if cursor + cell.cols > total:
        raise ValueError(
            f"{section_label} row {row_label!r}: rich cell with cols={cell.cols} "
            f"extends past the declared {total} data leaf column(s)"
        )
    _set_cell(
        row,
        cursor,
        LeafCell(
            value=cell.value,
            origin=(row_idx, cursor),
            rows=cell.rows,
            cols=cell.cols,
            align=cell.align,
        ),
        row_label=row_label,
        section_label=section_label,
    )
    for offset in range(1, cell.cols):
        _set_cell(
            row,
            cursor + offset,
            LeafCell(absorbed=True, origin=(row_idx, cursor)),
            row_label=row_label,
            section_label=section_label,
        )


# ---- row expansion with multirow carry-over ------------------------------


def _apply_active_spans(
    row: list[LeafCell | None],
    active: dict[int, tuple[int, int, int]],
    row_idx: int,
    section_label: str,
) -> None:
    for origin_col, (origin_row, rows_total, cols) in active.items():
        if row_idx >= origin_row + rows_total:
            continue
        for offset in range(cols):
            pos = origin_col + offset
            if row[pos] is not None:
                raise ValueError(
                    f"{section_label}: overlapping multirow spans at leaf column {pos}"
                )
            row[pos] = LeafCell(absorbed=True, origin=(origin_row, origin_col))


def _expand_data_row(
    data_row: DataRow,
    columns: list[Column],
    leaf_row: list[LeafCell | None],
    row_idx: int,
    section_label: str,
) -> list[LeafCell]:
    data_cols = columns[1:]
    n_leaves = len(leaf_row)
    cursor = 0
    col_index = 0
    col_leaf_start = 0

    def advance_to_cursor() -> None:
        nonlocal col_index, col_leaf_start
        while col_index < len(data_cols) and cursor >= col_leaf_start + leaf_count(
            data_cols[col_index]
        ):
            col_leaf_start += leaf_count(data_cols[col_index])
            col_index += 1

    def skip_absorbed() -> None:
        nonlocal cursor
        while cursor < n_leaves and leaf_row[cursor] is not None:
            cursor += 1
        advance_to_cursor()

    for cell in data_row.cells:
        if cursor < n_leaves and leaf_row[cursor] is not None:
            # Absorbed slot carried over from a multirow above.
            if cell is None:
                cursor += 1
                advance_to_cursor()
                continue
            raise ValueError(
                f"{section_label} row {data_row.label!r}: value written at leaf "
                f"column {cursor} which is absorbed by a multirow span above"
            )

        if col_index >= len(data_cols):
            raise ValueError(
                f"{section_label} row {data_row.label!r}: extra cell(s) beyond the "
                f"declared {len(data_cols)} data column(s)"
            )

        span = leaf_count(data_cols[col_index])

        if isinstance(cell, list):
            _place_list(cell, leaf_row, cursor, span, row_idx, data_row.label, section_label)
            cursor += span
            col_leaf_start += span
            col_index += 1
        elif isinstance(cell, RichCell):
            _place_rich(
                cell,
                leaf_row,
                cursor,
                row_idx,
                n_leaves,
                data_row.label,
                section_label,
            )
            cursor += cell.cols
            advance_to_cursor()
        else:
            _place_scalar(cell, leaf_row, cursor, span, row_idx, data_row.label, section_label)
            cursor += span
            col_leaf_start += span
            col_index += 1

        skip_absorbed()

    if cursor != n_leaves:
        raise ValueError(
            f"{section_label} row {data_row.label!r} covers {cursor} leaf cell(s); "
            f"expected {n_leaves}"
        )

    unfilled = [i for i, slot in enumerate(leaf_row) if slot is None]
    if unfilled:
        raise ValueError(
            f"{section_label} row {data_row.label!r} leaves leaf column(s) {unfilled} unfilled"
        )

    return [slot for slot in leaf_row if slot is not None]  # type: ignore[misc]


def _build_section(
    section_rows: list[Row],
    columns: list[Column],
    section_label: str,
    starting_row_index: int,
) -> tuple[list[list[LeafCell]], list[Literal["data", "separator"]], list[Separator]]:
    data_cols = columns[1:]
    n_leaves = total_leaves(data_cols)
    rows_out: list[list[LeafCell]] = []
    kinds: list[Literal["data", "separator"]] = []
    separators: list[Separator] = []
    active: dict[int, tuple[int, int, int]] = {}

    for i, row in enumerate(section_rows):
        absolute_row = starting_row_index + i

        if isinstance(row, Separator):
            if any(
                absolute_row < origin_row + rows_total
                for origin_row, rows_total, _ in active.values()
            ):
                raise ValueError(
                    f"{section_label} row {i}: separator falls inside an active multirow span"
                )
            rows_out.append([])
            kinds.append("separator")
            separators.append(row)
            continue

        leaf_row: list[LeafCell | None] = [None] * n_leaves
        _apply_active_spans(leaf_row, active, absolute_row, section_label)
        filled = _expand_data_row(row, columns, leaf_row, absolute_row, section_label)
        rows_out.append(filled)
        kinds.append("data")

        for col_idx, slot in enumerate(filled):
            if not slot.absorbed and slot.rows > 1:
                active[col_idx] = (absolute_row, slot.rows, slot.cols)

        active = {
            col: payload
            for col, payload in active.items()
            if absolute_row + 1 < payload[0] + payload[1]
        }

    if active:
        remaining = sorted(active)
        raise ValueError(
            f"{section_label}: multirow span(s) at leaf column(s) {remaining} "
            f"extend past the last row of the section"
        )

    return rows_out, kinds, separators


def build_matrix(table: Table) -> LeafMatrix:
    """Expand a :class:`Table` into dense leaf-level matrices.

    Raises :class:`ValueError` on any structural inconsistency (bad row width,
    unabsorbed multirow / multicolumn rectangles, span collisions, trailing
    spans extending past the end of a section, …).
    """
    body, body_kinds, body_seps = _build_section(
        list(table.rows), table.columns, "body", starting_row_index=0
    )
    footer, footer_kinds, footer_seps = _build_section(
        list(table.footer),
        table.columns,
        "footer",
        starting_row_index=len(table.rows),
    )
    return LeafMatrix(
        body=body,
        footer=footer,
        body_row_kinds=body_kinds,
        footer_row_kinds=footer_kinds,
        separators=body_seps,
        footer_separators=footer_seps,
    )


Cell = CellTopValue

__all__ = [
    "Align",
    "Cell",
    "CellLeafValue",
    "CellTopValue",
    "Column",
    "ColumnGroup",
    "DataRow",
    "LeafCell",
    "LeafColumn",
    "LeafMatrix",
    "RichCell",
    "Row",
    "Scalar",
    "Separator",
    "Table",
    "TableSettings",
    "build_matrix",
    "column_leaves",
    "header_depth",
    "leaf_count",
    "parse_table",
    "total_leaves",
]
