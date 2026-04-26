"""Tests for the YAML table schema, parser, and matrix validator."""

from __future__ import annotations

import re
import textwrap

from pydantic import ValidationError
import pytest
import yaml

from texsmith.extensions.tables import (
    ColumnGroup,
    DataRow,
    LeafColumn,
    RichCell,
    Separator,
    TableSettings,
    build_matrix,
    column_leaves,
    header_depth,
    leaf_count,
    parse_table,
    total_leaves,
)


def _load(src: str) -> dict:
    return yaml.safe_load(textwrap.dedent(src))


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------


def test_parses_simple_positional_table() -> None:
    table = parse_table(
        _load(
            """
            columns: [Produit, Genève, Lausanne, Zurich]
            rows:
              - [Pommes, 120, 80, 200]
              - [Poires, 45, ~, 90]
            footer:
              - [Total, 165, 80, 290]
            """
        )
    )
    assert [c.name for c in table.columns] == ["Produit", "Genève", "Lausanne", "Zurich"]
    assert all(isinstance(c, LeafColumn) for c in table.columns)
    assert len(table.rows) == 2
    assert isinstance(table.rows[0], DataRow)
    assert table.rows[0].label == "Pommes"
    assert table.rows[0].source == "positional"
    assert table.rows[1].cells == ["Poires", 45, None, 90][1:]
    assert len(table.footer) == 1


def test_parses_grouped_columns_with_width_group() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - Unité
              - name: Actuel
                columns: [S1, S2, S3, S4]
                width-group: "1"
              - name: V1
                columns: [S1, S2, S3, S4]
                width-group: "1"
            rows:
              - [Info 1, [6], [7]]
            """
        )
    )
    assert isinstance(table.columns[0], LeafColumn)
    group = table.columns[1]
    assert isinstance(group, ColumnGroup)
    assert group.name == "Actuel"
    assert group.width_group == "1"
    assert leaf_count(group) == 4
    assert total_leaves(table.columns[1:]) == 8
    assert header_depth(group) == 2


def test_parses_named_row_shorthand_and_explicit() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - Unité
              - name: Actuel
                columns: [S1, S2]
              - name: V1
                columns: [S1, S2]
            rows:
              - Info 1: {Actuel: [6], V1: [7]}
              - label: Info 2
                cells: {V1: [~, 9]}
            """
        )
    )
    first, second = table.rows
    assert isinstance(first, DataRow) and first.source == "named"
    assert first.label == "Info 1"
    # named → ordered list: [Actuel, V1]
    assert first.cells == [[6], [7]]
    assert isinstance(second, DataRow) and second.source == "named"
    assert second.label == "Info 2"
    assert second.cells == [None, [None, 9]]


def test_parses_leaf_column_metadata() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - name: Produit
                align: l
                width: 25%
              - name: Description
                align: j
              - name: Priorité
                align: c
                width: 15%
            rows:
              - [A, B, C]
            """
        )
    )
    produit = table.columns[0]
    assert isinstance(produit, LeafColumn)
    assert produit.align == "l"
    assert produit.width == "25%"
    assert table.columns[1].align == "j"
    assert table.columns[2].width == "15%"


def test_parses_table_settings() -> None:
    table = parse_table(
        _load(
            """
            table:
              width: 90%
              placement: H
              long: false
            columns: [A, B]
            rows:
              - [x, 1]
            """
        )
    )
    assert isinstance(table.settings, TableSettings)
    assert table.settings.width == "90%"
    assert table.settings.placement == "H"
    assert table.settings.long is False


def test_parses_separator_variants() -> None:
    table = parse_table(
        _load(
            """
            columns: [A, B]
            rows:
              - [x, 1]
              - separator: true
              - [y, 2]
              - separator: {label: "Section"}
              - [z, 3]
            """
        )
    )
    assert isinstance(table.rows[1], Separator)
    assert table.rows[1].label is None
    assert isinstance(table.rows[3], Separator)
    assert table.rows[3].label == "Section"


# ---------------------------------------------------------------------------
# Rich cells / spans
# ---------------------------------------------------------------------------


def test_rich_cell_multicol_spans_group() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - Unité
              - name: 2024
                columns: [Q1, Q2, Q3, Q4]
            rows:
              - [Ventes, [120, 130, 150, 170]]
              - [Total, {value: "545 k€", cols: 4, align: c}]
            """
        )
    )
    matrix = build_matrix(table)
    total_row = matrix.body[1]
    assert len(total_row) == 4
    origin = total_row[0]
    assert origin.value == "545 k€"
    assert origin.cols == 4
    assert origin.align == "c"
    assert all(c.absorbed for c in total_row[1:])
    assert all(c.origin == (1, 0) for c in total_row[1:])


def test_rich_cell_multirow_is_absorbed_by_tilde() -> None:
    table = parse_table(
        _load(
            """
            columns: [Projet, Évaluateur, Note, Commentaire]
            rows:
              - [Alpha, {value: Marie, rows: 2}, 17, "A"]
              - [Beta, ~, 14, "B"]
              - [Gamma, Paul, 12, "C"]
            """
        )
    )
    matrix = build_matrix(table)
    assert matrix.body[0][0].value == "Marie"
    assert matrix.body[0][0].rows == 2
    assert matrix.body[1][0].absorbed is True
    assert matrix.body[1][0].origin == (0, 0)
    assert matrix.body[2][0].value == "Paul"


def test_rich_cell_mixed_rectangle_is_fully_absorbed() -> None:
    table = parse_table(
        _load(
            """
            columns: [A, B, C, D]
            rows:
              - [r1, {value: "Bloc", rows: 2, cols: 3, align: c}]
              - [r2, ~, ~, ~]
              - [r3, x, y, z]
            """
        )
    )
    matrix = build_matrix(table)
    origin = matrix.body[0][0]
    assert origin.value == "Bloc"
    assert (origin.rows, origin.cols) == (2, 3)
    for col in range(3):
        assert matrix.body[1][col].absorbed is True
        assert matrix.body[1][col].origin == (0, 0)
    # Row r3 should be a normal data row with scalar values.
    assert [c.value for c in matrix.body[2]] == ["x", "y", "z"]


def test_rich_cell_align_override() -> None:
    table = parse_table(
        _load(
            """
            columns: [A, B]
            rows:
              - [r1, {value: 42, align: r}]
            """
        )
    )
    matrix = build_matrix(table)
    assert matrix.body[0][0].align == "r"
    assert matrix.body[0][0].value == 42


# ---------------------------------------------------------------------------
# Matrix content for non-span tables
# ---------------------------------------------------------------------------


def test_matrix_expands_scalar_over_grouped_column() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - Unité
              - name: 2024
                columns: [Q1, Q2]
            rows:
              - [Info, 99]
            """
        )
    )
    matrix = build_matrix(table)
    assert [c.value for c in matrix.body[0]] == [99, 99]
    # Spreading scalar is NOT a span: all cells have their own origin.
    assert matrix.body[0][0].origin == (0, 0)
    assert matrix.body[0][1].origin == (0, 1)


def test_matrix_pads_short_lists_with_none() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - Unité
              - name: 2024
                columns: [Q1, Q2, Q3]
            rows:
              - [Info, [5, 6]]
            """
        )
    )
    matrix = build_matrix(table)
    assert [c.value for c in matrix.body[0]] == [5, 6, None]


def test_separator_rows_appear_in_matrix_kinds() -> None:
    table = parse_table(
        _load(
            """
            columns: [A, B]
            rows:
              - [x, 1]
              - separator: true
              - [y, 2]
            """
        )
    )
    matrix = build_matrix(table)
    assert matrix.body_row_kinds == ["data", "separator", "data"]
    assert matrix.body[1] == []


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_rejects_missing_column() -> None:
    with pytest.raises(ValueError, match=re.escape("missing 'columns'")):
        parse_table({"rows": [[1]]})


def test_rejects_unknown_top_level_keys() -> None:
    with pytest.raises(ValueError, match="unknown top-level"):
        parse_table({"columns": ["A", "B"], "unknown": 1})


def test_rejects_short_row() -> None:
    with pytest.raises(Exception, match=r"covers \d+ leaf cell"):
        parse_table(
            _load(
                """
                columns: [A, B, C, D]
                rows:
                  - [x, 1, 2]
                """
            )
        )


def test_rejects_too_long_row() -> None:
    with pytest.raises(Exception, match="extra cell"):
        parse_table(
            _load(
                """
                columns: [A, B]
                rows:
                  - [x, 1, 2]
                """
            )
        )


def test_rejects_unknown_named_column() -> None:
    with pytest.raises(ValueError, match="unknown column"):
        parse_table(
            _load(
                """
                columns:
                  - Unité
                  - name: Actuel
                    columns: [S1, S2]
                rows:
                  - Info 1: {Acutel: [6]}
                """
            )
        )


def test_rejects_multirow_not_absorbed() -> None:
    with pytest.raises(Exception, match="absorbed by a multirow"):
        parse_table(
            _load(
                """
                columns: [A, B, C]
                rows:
                  - [r1, {value: x, rows: 2}, 1]
                  - [r2, oops, 2]
                """
            )
        )


def test_rejects_mixed_rectangle_not_absorbed() -> None:
    with pytest.raises(Exception, match=r"(absorbed|extra cell|expected)"):
        parse_table(
            _load(
                """
                columns: [A, B, C, D]
                rows:
                  - [r1, {value: Bloc, rows: 2, cols: 2}]
                  - [r2, a, b, c]
                """
            )
        )


def test_rejects_span_past_end_of_section() -> None:
    with pytest.raises(Exception, match="extend past"):
        parse_table(
            _load(
                """
                columns: [A, B]
                rows:
                  - [r1, {value: x, rows: 3}]
                  - [r2, ~]
                """
            )
        )


def test_rejects_separator_inside_active_span() -> None:
    with pytest.raises(Exception, match="separator falls inside"):
        parse_table(
            _load(
                """
                columns: [A, B]
                rows:
                  - [r1, {value: x, rows: 2}]
                  - separator: true
                  - [r2, ~]
                """
            )
        )


def test_rejects_invalid_width_percentage() -> None:
    with pytest.raises(Exception, match="percentage"):
        parse_table(
            _load(
                """
                table: {width: "150%"}
                columns: [A, B]
                rows: [[x, 1]]
                """
            )
        )


def test_rejects_invalid_placement() -> None:
    with pytest.raises(Exception, match="placement"):
        parse_table(
            _load(
                """
                table: {placement: "Z"}
                columns: [A, B]
                rows: [[x, 1]]
                """
            )
        )


def test_rejects_zero_rows_in_rich_cell() -> None:
    with pytest.raises(Exception, match=">="):
        parse_table(
            _load(
                """
                columns: [A, B]
                rows:
                  - [r1, {value: x, rows: 0}]
                """
            )
        )


def test_rejects_rich_cell_cols_past_total() -> None:
    with pytest.raises(Exception, match="extends past"):
        parse_table(
            _load(
                """
                columns: [A, B, C]
                rows:
                  - [r1, {value: x, cols: 5}]
                """
            )
        )


def test_rejects_single_column_table() -> None:
    # Tables need at least a label column + one data column.
    with pytest.raises(ValidationError, match="at least 2 items"):
        parse_table(_load("columns: [A]\nrows: []\n"))


# ---------------------------------------------------------------------------
# End-to-end: all happy-path examples from examples/tables/tables.md
# ---------------------------------------------------------------------------


_EXAMPLES = {
    "stocks": """
        columns: [Produit, Genève, Lausanne, Zurich]
        rows:
          - [Pommes,   120, 80, 200]
          - [Poires,   45,  ~,  90]
          - separator: {label: En rupture possible}
          - [Abricots, 5,   0,  2]
        footer:
          - [Total, 170, 80, 292]
    """,
    "repartition_horaire": """
        table:
          width: 100%
        columns:
          - Unité
          - name: Actuel
            columns: [S1, S2, S3, S4]
            width-group: "1"
          - name: V1
            columns: [S1, S2, S3, S4]
            width-group: "1"
          - name: V2
            columns: [S1, S2, S3, S4]
            width-group: "1"
          - name: V3
            columns: [S1, S2, S3, S4]
            width-group: "1"
        rows:
          - [Info 1,    [6], [7], [4], []]
          - [Info 2,    [~, 5], [~, 2], [~, 5], []]
          - [PythonGE1, [~, 2], [2], [~, 2], []]
          - [PythonGE2, [~, ~, 3], [~, ~, 3], [~, ~, 3], [~, ~, 3]]
          - [MicroInfo, [5], [~, 5], [5], [~, ~, 3]]
          - separator: true
          - [CalcNum,   [], [], [], [3]]
          - [Python1,   [], [], [], [6]]
          - [ProgC,     [], [], [], [~, 7]]
        footer:
          - [Total, [11,2,3,0], [7,2,3,0], [4,7,3,0], [9,4,3,0]]
          - [Σ,     16,         12,        14,        16]
    """,
    "named_mode": """
        columns:
          - Unité
          - name: Actuel
            columns: [S1, S2, S3, S4]
          - name: V1
            columns: [S1, S2, S3, S4]
        rows:
          - Info 1: {Actuel: [6], V1: [7]}
          - Info 2: {Actuel: [~, 5], V1: [~, 2]}
          - PythonGE2: {Actuel: [~, ~, 3], V1: [~, ~, 3]}
          - separator: true
          - label: Python1
            cells: {V1: [6]}
    """,
    "three_levels": """
        columns:
          - Produit
          - name: 2024
            columns:
              - name: Q1
                columns: [Jan, Fév, Mar]
              - name: Q2
                columns: [Avr, Mai, Jun]
        rows:
          - [Alpha, [10, 12, 15, 18, 20, 22]]
          - [Beta,  [~,  ~,  5,  8,  10, 12]]
    """,
    "multirow": """
        columns: [Projet, Évaluateur, Note, Commentaire]
        rows:
          - [Alpha, {value: Marie, rows: 2}, 17, "Très bon rendu"]
          - [Beta,  ~,                       14, "À retravailler"]
          - [Gamma, Paul,                    12, "Incomplet"]
    """,
    "multicol": """
        columns:
          - Unité
          - name: 2024
            columns: [Q1, Q2, Q3, Q4]
        rows:
          - [Ventes, [120, 130, 150, 170]]
          - [Coûts,  [80,  85,  90,  95]]
          - separator: true
          - [Total, {value: "545 k€", cols: 4, align: c}]
    """,
    "mixed_block": """
        columns: [A, B, C, D]
        rows:
          - [r1, {value: "Bloc fusionné", rows: 2, cols: 3, align: c}]
          - [r2, ~, ~, ~]
          - [r3, x, y, z]
    """,
    "widths_mix": """
        table:
          width: 90%
        columns:
          - name: Exigence
            width: 25%
            align: l
          - name: Description
            align: j
          - name: Priorité
            width: 15%
            align: c
        rows:
          - [EX-001, "Import CSV.", Haute]
          - [EX-002, "Export PDF.", Moyenne]
    """,
    "widths_group": """
        table:
          width: 100%
        columns:
          - Poste
          - name: Q1
            width-group: trimestre
          - name: Q2
            width-group: trimestre
          - name: Q3
            width-group: trimestre
          - name: Q4
            width-group: trimestre
        rows:
          - [Salaires, 120000, 122000, 121000, 125000]
        footer:
          - [Total, 165000, 162000, 171000, 171000]
    """,
}


@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_parses_all_happy_examples(name: str) -> None:
    table = parse_table(_load(_EXAMPLES[name]))
    matrix = build_matrix(table)
    # Sanity: every data row has exactly total_leaves(data_cols) cells.
    expected = total_leaves(table.columns[1:])
    rows = matrix.body + matrix.footer
    kinds = matrix.body_row_kinds + matrix.footer_row_kinds
    for row, kind in zip(rows, kinds, strict=True):
        if kind == "data":
            assert len(row) == expected


# ---------------------------------------------------------------------------
# RichCell type coverage
# ---------------------------------------------------------------------------


def test_rich_cell_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError, match="unknown"):
        RichCell(value=1, rows=1, cols=1, unknown=True)


def test_leaf_column_rejects_extra_keys() -> None:
    with pytest.raises(ValidationError, match="foo"):
        LeafColumn(name="A", foo=1)


# ---------------------------------------------------------------------------
# Long-form alignment + explicit X width
# ---------------------------------------------------------------------------


def test_align_accepts_long_forms() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - {name: A, align: left}
              - {name: B, align: right}
              - {name: C, align: center}
              - {name: D, align: justify}
            rows: [[a, 1, 2, 3]]
            """
        )
    )
    assert [c.align for c in table.columns] == ["l", "r", "c", "j"]


def test_align_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError, match="invalid align"):
        LeafColumn(name="A", align="diagonal")


def test_width_accepts_explicit_x_marker() -> None:
    col = LeafColumn(name="A", width="X")
    assert col.width == "X"
    # Lowercase ``x`` normalises to ``X``.
    col = LeafColumn(name="B", width="x")
    assert col.width == "X"


# ---------------------------------------------------------------------------
# TableConfig parsing (yaml table-config payload)
# ---------------------------------------------------------------------------


def test_table_config_parses_basic_payload() -> None:
    from texsmith.extensions.tables import parse_table_config, synthesise_table_for_config

    config = parse_table_config(
        _load(
            """
            table:
              width: 90%
            columns:
              - {align: left}
              - {align: right}
              - {align: justify, width: X}
            """
        )
    )
    assert config.settings.width == "90%"
    assert len(config.columns) == 3
    assert config.columns[2].width == "X"

    synthetic = synthesise_table_for_config(config, n_columns=3)
    assert [c.align for c in synthetic.columns] == ["l", "r", "j"]
    assert synthetic.columns[2].width == "X"


def test_table_config_columns_default_to_natural_when_missing() -> None:
    from texsmith.extensions.tables import parse_table_config, synthesise_table_for_config

    config = parse_table_config(_load("columns: []"))
    synthetic = synthesise_table_for_config(config, n_columns=4)
    assert all(c.align is None for c in synthetic.columns)
    assert all(c.width is None for c in synthetic.columns)


def test_table_config_rejects_unknown_keys() -> None:
    from texsmith.extensions.tables import parse_table_config

    with pytest.raises(ValueError, match="unknown top-level"):
        parse_table_config({"columns": [], "weird": True})


# ---------------------------------------------------------------------------
# Headerless columns
# ---------------------------------------------------------------------------


def test_leaf_column_name_is_optional() -> None:
    table = parse_table(
        _load(
            """
            table:
              width: 100%
            columns:
              - align: l
                width: 40%
              - align: j
            rows:
              - ["Project codename", "Northwind"]
              - ["Theory ratio", "50%"]
            """
        )
    )
    assert all(col.name is None for col in table.columns)
    assert isinstance(table.columns[0], LeafColumn)
    assert table.columns[0].align == "l"
    assert table.columns[0].width == "40%"
    assert isinstance(table.rows[0], DataRow)
    assert table.rows[0].label == "Project codename"
    assert table.rows[0].cells == ["Northwind"]


def test_headerless_table_builds_full_matrix() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - align: l
              - align: r
            rows:
              - [Alpha, 1]
              - [Beta, 2]
            """
        )
    )
    matrix = build_matrix(table)
    assert [c.value for c in matrix.body[0]] == [1]
    assert [c.value for c in matrix.body[1]] == [2]


def test_grouped_column_still_requires_name() -> None:
    with pytest.raises(ValueError, match="grouped column is missing 'name'"):
        parse_table(
            _load(
                """
                columns:
                  - A
                  - columns: [Q1, Q2]
                rows:
                  - [x, [1, 2]]
                """
            )
        )


def test_named_row_against_unnamed_data_column_is_unknown() -> None:
    with pytest.raises(ValueError, match="unknown column"):
        parse_table(
            _load(
                """
                columns:
                  - Label
                  - align: j
                rows:
                  - Foo: {Anything: bar}
                """
            )
        )


def test_column_leaves_traverses_nested_groups() -> None:
    table = parse_table(
        _load(
            """
            columns:
              - Produit
              - name: 2024
                columns:
                  - name: Q1
                    columns: [Jan, Fév]
                  - name: Q2
                    columns: [Avr]
            rows:
              - [A, [1, 2, 3]]
            """
        )
    )
    leaves = column_leaves(table.columns[1])
    assert [leaf.name for leaf in leaves] == ["Jan", "Fév", "Avr"]
