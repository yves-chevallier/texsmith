"""Yaml-table extension for TeXSmith.

The public API is intentionally narrow for now: only the schema and the
parser are exported. Markdown/HTML/LaTeX bindings live in their own modules
and will be wired in later.
"""

from __future__ import annotations

from .html import render_error_html, render_table_html
from .layout import ColumnLayout, TableEnv, TableLayout, compute_layout
from .markdown import YamlTableExtension, makeExtension
from .renderer import register as register_renderer, render_yaml_table
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
    "ColumnLayout",
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
    "TableEnv",
    "TableLayout",
    "TableSettings",
    "YamlTableExtension",
    "build_matrix",
    "column_leaves",
    "compute_layout",
    "header_depth",
    "leaf_count",
    "makeExtension",
    "parse_table",
    "parse_table_config",
    "register_renderer",
    "render_error_html",
    "render_table_html",
    "render_yaml_table",
    "synthesise_table_for_config",
    "total_leaves",
]
