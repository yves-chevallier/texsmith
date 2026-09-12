"""The validated table model the HTML reader rebuilds a ``<table>`` into.

What is left of the ``yaml table`` extension after phase 5: the schema and its
parser. tmark parses the ``yaml table`` fences now, and the tmark table model
supersedes this one for every Markdown source; :mod:`texsmith.readers.html`
still reconstructs a ``<table>`` through :func:`parse_table`'s model — column
groups, spans, separators and alignment — before mapping it onto
:class:`texsmith.ir.model.TableModel`.
"""

from __future__ import annotations

from .schema import (
    Align,
    Cell,
    Column,
    ColumnConfig,
    ColumnGroup,
    DataRow,
    LeafCell,
    LeafColumn,
    LeafMatrix,
    RichCell,
    Row,
    Scalar,
    Separator,
    Table,
    TableConfig,
    TableSettings,
    build_matrix,
    column_leaves,
    header_depth,
    leaf_count,
    parse_table,
    parse_table_config,
    synthesise_table_for_config,
    total_leaves,
)


__all__ = [
    "Align",
    "Cell",
    "Column",
    "ColumnConfig",
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
    "TableConfig",
    "TableSettings",
    "build_matrix",
    "column_leaves",
    "header_depth",
    "leaf_count",
    "parse_table",
    "parse_table_config",
    "synthesise_table_for_config",
    "total_leaves",
]
