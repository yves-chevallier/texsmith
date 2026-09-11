"""The ``title`` pass: title promotion and ``--strip-heading`` on the IR."""

from __future__ import annotations

from texsmith.core.documents import TitleStrategy
from texsmith.ir import model


def test_promotion_drops_the_unique_first_header(harness) -> None:
    document = harness.load("title", "promote", title_strategy=TitleStrategy.PROMOTE_METADATA)
    assert document.extracted_title == "Promoted Title"
    assert document.drop_title is True

    out = harness.run("title", document)
    assert out is not document
    assert out.ir is not None and document.ir is not None
    assert isinstance(out.ir.blocks[0], model.Para)
    assert [b.level for b in out.ir.blocks if isinstance(b, model.Header)] == [2]
    # The prepared decision travels with the evolved document.
    assert out.drop_title is True
    assert out.extracted_title == "Promoted Title"
    # The input is untouched.
    assert isinstance(document.ir.blocks[0], model.Header)
    assert harness.structural(out) == harness.expected("title", "promote")


def test_level_shared_by_two_headers_is_kept(harness) -> None:
    document = harness.load("title", "keep", title_strategy=TitleStrategy.PROMOTE_METADATA)
    assert document.extracted_title is None
    assert document.drop_title is False
    assert harness.run("title", document) is document


def test_drop_strategy_removes_the_first_header(harness) -> None:
    document = harness.load("title", "keep", title_strategy=TitleStrategy.DROP)
    out = harness.run("title", document)
    assert out.ir is not None
    headers = [b for b in out.ir.blocks if isinstance(b, model.Header)]
    assert len(headers) == 1
    assert harness.structural(out) == harness.expected("title", "keep")


def test_keep_strategy_is_identity(harness) -> None:
    document = harness.load("title", "promote")
    assert harness.run("title", document) is document
