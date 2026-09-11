"""The ``var`` pass: moustaches in the body."""

from __future__ import annotations

from texsmith.ir import model
from texsmith.ir.walk import plain_text, walk


def test_scalars_become_str_lists_and_missing_paths_are_reported(harness) -> None:
    document = harness.load("var", "basic")
    ctx = harness.context(
        document, contexts=({"press": {"template": "article"}}, document.front_matter)
    )
    floor = ctx.ids.floor
    out = harness.run("var", document, ctx)

    assert out is not document
    assert document.ir is not out.ir and document.ir is not None and out.ir is not None
    header = out.ir.blocks[0]
    assert isinstance(header, model.Header)
    assert plain_text(header.content) == "Hello"

    remaining = [node for node in walk(out.ir) if isinstance(node, model.Var)]
    assert [node.path for node in remaining] == [("authors",), ("missing", "path")]
    assert [record.code for record in ctx.diagnostics] == ["var-not-scalar", "var-unresolved"]

    # Span rule 2: the Str takes the Var's span and a fresh id.
    source_var = next(node for node in walk(document.ir) if isinstance(node, model.Var))
    replacement = next(
        node for node in walk(out.ir) if isinstance(node, model.Str) and node.text == "Hello"
    )
    assert replacement.span == source_var.span
    assert floor <= replacement.id < ctx.ids.floor
    assert all(replacement.id != node.id for node in walk(document.ir))

    # The moustache inside a code span was never a Var.
    codes = [node.text for node in walk(out.ir) if isinstance(node, model.Code)]
    assert codes == ["{{ title }}"]

    assert harness.structural(out) == harness.expected("var", "basic")
    assert harness.diagnostics(ctx) == harness.expected_diagnostics("var", "basic")


def test_pass_is_identity_without_vars(harness) -> None:
    document = harness.load("stubs", "plain")
    assert harness.run("var", document) is document
