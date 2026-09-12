"""The ``scripts`` pass: ``Span{script}`` runs, math letters, the font summary."""

from __future__ import annotations

from texsmith.ir import model
from texsmith.ir.walk import plain_text, walk
from texsmith.passes.scripts import document_text


def _spans(document) -> list[model.SpanNode]:
    return [
        node
        for node in walk(document.ir)
        if isinstance(node, model.SpanNode) and "script" in dict(node.attrs.kv)
    ]


def _context(harness, document, detector):
    ctx = harness.context(document)
    ctx.values["script_detector"] = detector
    return ctx


def test_runs_math_letters_and_summary(harness, fake_script_detector) -> None:
    document = harness.load("scripts", "runs")
    ctx = _context(harness, document, fake_script_detector)
    floor = ctx.ids.floor
    after_emoji = harness.run("emoji", document, ctx)
    out = harness.run("scripts", after_emoji, ctx)

    assert out is not after_emoji
    assert harness.structural(out) == harness.expected("scripts", "runs")
    assert len(ctx.diagnostics) == 0

    spans = _spans(out)
    assert [(dict(node.attrs.kv)["script"], plain_text(node.content)) for node in spans] == [
        ("cyrillics", "Привет мир "),  # whitespace joins inside a run
        ("japanese", "日本語のテキスト "),  # the CJK vote: kana outnumber ideographs
        ("cyrillics", "Жирный"),
        ("tibetan", "བོད་ཡིག"),
        ("cyrillics", "Жирный"),  # the lead-in paragraph
    ]
    # A lone Greek or Hebrew letter is math (``fonts/scripts.py:89-113``).
    assert [node.text for node in walk(out.ir) if isinstance(node, model.Math)] == [
        "\\Omega",
        "\\aleph",
    ]
    # Code is untouched, the emoji span is fenced off, ASCII text is shared.
    assert [node.text for node in walk(out.ir) if isinstance(node, model.Code)] == ["код"]
    spans_by_key = [dict(node.attrs.kv) for node in walk(out.ir) if isinstance(node, model.SpanNode)]
    assert {"emoji": "😀"} in spans_by_key
    assert out.ir.blocks[0] is document.ir.blocks[0]

    # Span rule 2: a span and its text take the source ``Str``'s span, fresh ids.
    source = document.ir.blocks[1].content[0]
    assert spans[0].span == source.span == spans[0].content[0].span
    assert all(node.id >= floor for node in spans)

    usage = {entry["slug"]: entry for entry in ctx.values["script_usage"]}
    # The lone letters left as math macros: no Greek/Symbols font is needed.
    assert set(usage) == {"cyrillics", "japanese", "tibetan", "chinese", "emoji"}
    assert usage["cyrillics"]["font_name"] == "NotoSans"
    assert usage["cyrillics"]["text_command"] == "textcyrillics"
    assert usage["emoji"]["text_command"] == "texsmithEmoji"
    assert usage["cyrillics"]["count"] >= len("Привет мир ") + len("Жирный")
    classes = {entry["class"] for entry in ctx.values["fallback_summary"]}
    assert {"Cyrillic", "Hiragana", "Katakana", "CJKUnifiedIdeographs", "Emoticons"} <= classes

    # Idempotent over its own spans.
    again = harness.run("scripts", out, _context(harness, out, fake_script_detector))
    assert again is out


def test_document_text_covers_every_text_node(harness) -> None:
    document = harness.load("stubs", "plain")
    text = document_text(document.ir)
    assert "Plain" in text and "code" in text and 'print("hi")' in text


def test_intended_difference_with_the_legacy_wrapper(harness, fake_script_detector) -> None:
    """A run next to emphasis or math is wrapped: the legacy skipped such paragraphs."""
    document = harness.load("scripts", "runs")
    ctx = _context(harness, document, fake_script_detector)
    out = harness.run("scripts", document, ctx)
    # The paragraph that is one strong span is the lead-in (tmark C44); the
    # one that merely starts with a strong span keeps it inline. Both carry a
    # Cyrillic run the legacy wrapper would have skipped.
    lead = out.ir.blocks[4].lead
    assert lead is not None and isinstance(lead[0], model.SpanNode)
    assert dict(lead[0].attrs.kv) == {"script": "cyrillics"}
    strong = out.ir.blocks[3].content[0]
    assert isinstance(strong, model.Strong)
    assert dict(strong.content[0].attrs.kv) == {"script": "cyrillics"}


def test_identity_for_ascii_documents(harness, fake_script_detector) -> None:
    document = harness.load("stubs", "plain")
    ctx = _context(harness, document, fake_script_detector)
    assert harness.run("scripts", document, ctx) is document
    assert "script_usage" not in ctx.values and "fallback_summary" not in ctx.values


def test_offline_detector_degrades_to_no_spans(harness) -> None:
    """Without font metadata the detector classifies nothing; the text stays as written."""
    from texsmith.fonts.fallback import FallbackIndex, FallbackLookup
    from texsmith.fonts.scripts import ScriptDetector

    detector = ScriptDetector()
    detector._lookup = FallbackLookup(FallbackIndex([]))
    document = harness.load("scripts", "runs")
    ctx = _context(harness, document, detector)
    out = harness.run("scripts", document, ctx)
    # One unclassified run per ``Str``: no span, and the lone letters are not
    # alone in their chunk, so no math either (the legacy detector's rule).
    assert out is document
    # The summary still reports the unclassified characters, as the legacy scan did.
    assert [entry["slug"] for entry in ctx.values["script_usage"]] == ["unknown"]
