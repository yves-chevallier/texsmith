"""The ``Diagnostic`` record, its JSON shape and the tmark round trip."""

from __future__ import annotations

import dataclasses

import pytest

from texsmith.diagnostics import NO_SPAN, Diagnostic, Fix, Severity, Span, from_tmark


def test_severities_are_tmark_words_in_order() -> None:
    assert [s.value for s in Severity] == ["hint", "info", "warning", "error"]
    assert Severity.HINT < Severity.INFO < Severity.WARNING < Severity.ERROR
    assert Severity.WARNING >= Severity.WARNING
    assert max(Severity.INFO, Severity.ERROR) is Severity.ERROR
    assert Severity("warning") is Severity.WARNING


def test_span_serialises_as_a_triple() -> None:
    span = Span(1, 3, 9)
    assert span.to_json() == [1, 3, 9]
    assert Span.from_json([1, 3, 9]) == span
    assert Span.from_json((1, 3, 9)) == span
    assert Span(0, 0, 0) == NO_SPAN
    with pytest.raises(ValueError, match="triple"):
        Span.from_json([1, 2])


def test_diagnostic_is_frozen() -> None:
    diagnostic = Diagnostic("asset-missing", Severity.WARNING, NO_SPAN, "gone")
    with pytest.raises(dataclasses.FrozenInstanceError):
        diagnostic.message = "changed"  # type: ignore[misc]
    assert diagnostic.key == ("asset-missing", NO_SPAN, "gone")
    assert diagnostic.origin == "texsmith"


def test_to_json_skips_empty_fix_and_related() -> None:
    plain = Diagnostic("asset-missing", Severity.WARNING, Span(0, 4, 12), "gone")
    assert plain.to_json() == {
        "code": "asset-missing",
        "severity": "warning",
        "span": [0, 4, 12],
        "message": "gone",
        "origin": "texsmith",
    }
    rich = Diagnostic(
        "deprecated",
        Severity.WARNING,
        Span(0, 4, 12),
        "`[^k]` is a citation; write `@k`",
        fix=Fix(Span(0, 4, 12), "@k"),
        related=((Span(0, 40, 44), "the footnote definition"),),
        origin="tmark",
    )
    assert rich.to_json() == {
        "code": "deprecated",
        "severity": "warning",
        "span": [0, 4, 12],
        "message": "`[^k]` is a citation; write `@k`",
        "fix": {"span": [0, 4, 12], "replacement": "@k"},
        "related": [[[0, 40, 44], "the footnote definition"]],
        "origin": "tmark",
    }


def test_from_tmark_reads_the_serde_shape() -> None:
    # ``serde`` skips ``fix`` when ``None`` and ``related`` when empty.
    record = {
        "code": "ref-unresolved",
        "severity": "warning",
        "span": [0, 20, 31],
        "message": "`@fig:missing` does not resolve",
    }
    diagnostic = from_tmark(record)
    assert diagnostic == Diagnostic(
        "ref-unresolved",
        Severity.WARNING,
        Span(0, 20, 31),
        "`@fig:missing` does not resolve",
        origin="tmark",
    )
    assert diagnostic.fix is None
    assert diagnostic.related == ()


def test_from_tmark_round_trips_fix_and_related() -> None:
    record = {
        "code": "label-duplicate",
        "severity": "warning",
        "span": [2, 8, 15],
        "message": "label `fig:a` defined twice",
        "fix": {"span": [2, 8, 15], "replacement": "fig:a2"},
        "related": [[[2, 1, 6], "first definition"]],
    }
    diagnostic = from_tmark(record)
    assert diagnostic.fix == Fix(Span(2, 8, 15), "fig:a2")
    assert diagnostic.related == ((Span(2, 1, 6), "first definition"),)
    assert diagnostic.to_json() == {**record, "origin": "tmark"}


def test_from_tmark_rejects_an_unknown_severity() -> None:
    with pytest.raises(ValueError, match="fatal"):
        from_tmark({"code": "x", "severity": "fatal", "span": [0, 0, 0], "message": "m"})
