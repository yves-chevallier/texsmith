"""Tests for the yaml-table layout resolver."""

from __future__ import annotations

import textwrap

import pytest
import yaml

from texsmith.extensions.tables import compute_layout, parse_table


def _layout(src: str):
    return compute_layout(parse_table(yaml.safe_load(textwrap.dedent(src))))


# ---------------------------------------------------------------------------
# Environment selection
# ---------------------------------------------------------------------------


def test_chooses_tabular_when_width_is_auto() -> None:
    layout = _layout(
        """
        columns: [A, B, C]
        rows: [[x, 1, 2]]
        """
    )
    assert layout.env == "tabular"
    assert layout.total_width_spec is None
    assert layout.colspec == "lll"


def test_chooses_tabularx_when_table_width_and_auto_columns() -> None:
    layout = _layout(
        """
        table: {width: 100%}
        columns: [A, B, C]
        rows: [[x, 1, 2]]
        """
    )
    assert layout.env == "tabularx"
    assert layout.total_width_spec == r"\linewidth"
    # All three leaves are auto → all X with raggedright wrapper (default align=l).
    assert layout.colspec.count("X") == 3
    assert r">{\raggedright\arraybackslash}X" in layout.colspec


def test_percent_width_becomes_fraction_of_linewidth() -> None:
    layout = _layout(
        """
        table: {width: 80%}
        columns: [A, B]
        rows: [[x, 1]]
        """
    )
    assert layout.total_width_spec == r"0.8\linewidth"


def test_falls_back_to_tabular_when_all_columns_fixed() -> None:
    layout = _layout(
        """
        table: {width: 100%}
        columns:
          - {name: A, width: 30%}
          - {name: B, width: 70%}
        rows: [[x, 1]]
        """
    )
    # tabularx would warn without an X column → fall back to tabular.
    assert layout.env == "tabular"
    assert layout.total_width_spec is None
    assert r"p{0.3\linewidth}" in layout.colspec
    assert r"p{0.7\linewidth}" in layout.colspec


def test_longtable_when_settings_long_true() -> None:
    layout = _layout(
        """
        table: {long: true}
        columns: [A, B]
        rows: [[x, 1]]
        """
    )
    assert layout.env == "longtable"


def test_placement_passed_through() -> None:
    layout = _layout(
        """
        table: {placement: "H"}
        columns: [A, B]
        rows: [[x, 1]]
        """
    )
    assert layout.placement == "H"


# ---------------------------------------------------------------------------
# Column alignment
# ---------------------------------------------------------------------------


def test_default_alignment_is_left_in_tabular() -> None:
    layout = _layout(
        """
        columns: [A, B, C]
        rows: [[x, 1, 2]]
        """
    )
    assert layout.colspec == "lll"


def test_leaf_align_respected_in_tabular() -> None:
    layout = _layout(
        """
        columns:
          - A
          - {name: B, align: c}
          - {name: C, align: r}
        rows: [[x, 1, 2]]
        """
    )
    assert layout.colspec == "lcr"


def test_align_justified_without_width_falls_back_to_left_in_tabular() -> None:
    layout = _layout(
        """
        columns:
          - A
          - {name: B, align: j}
        rows: [[x, "longue phrase"]]
        """
    )
    # 'j' without a p{} width is meaningless in tabular → degrade to 'l'.
    assert layout.colspec == "ll"


def test_align_justified_with_width_uses_plain_pbox() -> None:
    layout = _layout(
        """
        columns:
          - A
          - {name: B, align: j, width: "30%"}
        rows: [[x, "longue phrase"]]
        """
    )
    assert layout.columns[1].align == "j"
    assert r"p{0.3\linewidth}" in layout.colspec
    # Justified columns don't wrap the p{} with raggedright/centering/etc.
    assert r">{\raggedright\arraybackslash}p{0.3\linewidth}" not in layout.colspec


def test_align_with_fixed_width_wraps_pbox() -> None:
    layout = _layout(
        """
        columns:
          - A
          - {name: B, align: c, width: "20%"}
          - {name: C, align: r, width: "10%"}
        rows: [[x, 1, 2]]
        """
    )
    assert r">{\centering\arraybackslash}p{0.2\linewidth}" in layout.colspec
    assert r">{\raggedleft\arraybackslash}p{0.1\linewidth}" in layout.colspec


def test_align_with_x_column_wraps_x() -> None:
    layout = _layout(
        """
        table: {width: 100%}
        columns:
          - A
          - {name: B, align: r}
        rows: [[x, 1]]
        """
    )
    assert layout.env == "tabularx"
    assert r">{\raggedleft\arraybackslash}X" in layout.colspec


# ---------------------------------------------------------------------------
# Inheritance from ColumnGroup
# ---------------------------------------------------------------------------


def test_group_align_propagates_to_leaves() -> None:
    layout = _layout(
        """
        columns:
          - Unité
          - name: 2024
            align: r
            columns: [Q1, Q2]
        rows: [[x, [1, 2]]]
        """
    )
    # Label leaf defaults to 'l', then two data leaves align='r'.
    assert [c.align for c in layout.columns] == ["l", "r", "r"]


def test_leaf_align_overrides_group_align() -> None:
    layout = _layout(
        """
        columns:
          - Unité
          - name: 2024
            align: r
            columns:
              - Q1
              - {name: Q2, align: c}
        rows: [[x, [1, 2]]]
        """
    )
    assert [c.align for c in layout.columns] == ["l", "r", "c"]


def test_group_width_is_distributed_across_leaves() -> None:
    layout = _layout(
        """
        columns:
          - Unité
          - name: 2024
            width: "40%"
            columns: [Q1, Q2, Q3, Q4]
        rows: [[x, [1, 2, 3, 4]]]
        """
    )
    # 40% / 4 = 10% per leaf → 0.1\linewidth.
    for col in layout.columns[1:]:
        assert col.width_spec == r"0.1\linewidth"


def test_leaf_width_overrides_group_share() -> None:
    layout = _layout(
        """
        columns:
          - Unité
          - name: 2024
            width: "40%"
            columns:
              - Q1
              - {name: Q2, width: "25%"}
        rows: [[x, [1, 2]]]
        """
    )
    # Q1 inherits 20% from group (40% / 2); Q2 keeps its own 25%.
    assert layout.columns[1].width_spec == r"0.2\linewidth"
    assert layout.columns[2].width_spec == r"0.25\linewidth"


# ---------------------------------------------------------------------------
# Width groups
# ---------------------------------------------------------------------------


def test_width_group_equalises_leaves_from_first_explicit() -> None:
    layout = _layout(
        """
        columns:
          - Poste
          - {name: A, width: "20%", "width-group": g}
          - {name: B, "width-group": g}
          - {name: C, "width-group": g}
        rows: [[x, 1, 2, 3]]
        """
    )
    # All three members of group 'g' collapse to 20%.
    for col in layout.columns[1:]:
        assert col.width_spec == r"0.2\linewidth"
        assert col.width_group == "g"


def test_width_group_on_parent_propagates_to_leaves() -> None:
    layout = _layout(
        """
        table: {width: 100%}
        columns:
          - Unité
          - name: Actuel
            columns: [S1, S2, S3, S4]
            width-group: "1"
          - name: V1
            columns: [S1, S2, S3, S4]
            width-group: "1"
        rows:
          - [Info, [1, 2, 3, 4], [5, 6, 7, 8]]
        """
    )
    # 9 leaves total (1 label + 8 data). The 8 data leaves belong to group '1'
    # → they become ``X`` and share ``\linewidth``. The label column has no
    # group and no width, so it keeps its natural width (plain ``l``) instead
    # of stealing a ninth slice of the line.
    assert layout.env == "tabularx"
    assert layout.columns[0].width_group is None
    assert layout.colspec.count("X") == 8
    assert layout.colspec.startswith("l")


def test_non_group_label_column_stays_natural_when_groups_exist() -> None:
    # When at least one column participates in a width-group, non-group
    # columns without an explicit width must keep their natural width — only
    # width-group members absorb the declared total width.
    layout = _layout(
        """
        table: {width: 100%}
        columns:
          - Label
          - {name: A, "width-group": g}
          - {name: B, "width-group": g}
        rows: [[x, 1, 2]]
        """
    )
    assert layout.env == "tabularx"
    assert layout.columns[0].align == "l"
    assert layout.colspec.startswith("l")
    assert layout.colspec.count("X") == 2


def test_width_group_auto_stays_auto() -> None:
    layout = _layout(
        """
        table: {width: 100%}
        columns:
          - Poste
          - {name: A, "width-group": g}
          - {name: B, "width-group": g}
        rows: [[x, 1, 2]]
        """
    )
    assert layout.env == "tabularx"
    assert all(col.width_spec is None for col in layout.columns)


# ---------------------------------------------------------------------------
# End-to-end on the canonical examples from tables.md
# ---------------------------------------------------------------------------


_EXAMPLES = {
    "stocks_auto": (
        """
        columns: [Produit, Genève, Lausanne, Zurich]
        rows:
          - [Pommes, 120, 80, 200]
        """,
        "tabular",
    ),
    "full_width_grouped": (
        """
        table: {width: 100%}
        columns:
          - Unité
          - name: Actuel
            columns: [S1, S2, S3, S4]
            width-group: "1"
          - name: V1
            columns: [S1, S2, S3, S4]
            width-group: "1"
        rows:
          - [Info, [1, 2, 3, 4], [5, 6, 7, 8]]
        """,
        "tabularx",
    ),
    "fixed_plus_auto": (
        """
        table: {width: 90%}
        columns:
          - {name: Exigence, width: "25%", align: l}
          - {name: Description, align: j}
          - {name: Priorité, width: "15%", align: c}
        rows:
          - [EX1, "Import CSV.", Haute]
        """,
        "tabularx",
    ),
    "equal_width_group": (
        """
        table: {width: 100%}
        columns:
          - Poste
          - {name: Q1, "width-group": t}
          - {name: Q2, "width-group": t}
          - {name: Q3, "width-group": t}
          - {name: Q4, "width-group": t}
        rows:
          - [Salaires, 1, 2, 3, 4]
        """,
        "tabularx",
    ),
}


@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_canonical_examples_select_expected_env(name: str) -> None:
    src, expected_env = _EXAMPLES[name]
    layout = _layout(src)
    assert layout.env == expected_env


def test_fixed_plus_auto_builds_expected_colspec() -> None:
    layout = _layout(_EXAMPLES["fixed_plus_auto"][0])
    assert layout.total_width_spec == r"0.9\linewidth"
    # Three columns: fixed left, flexible justified, fixed centred.
    assert layout.colspec == (
        r">{\raggedright\arraybackslash}p{0.25\linewidth}"
        r"X"
        r">{\centering\arraybackslash}p{0.15\linewidth}"
    )
