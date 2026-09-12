"""The ``glossary`` pass: ``press.declare.glossary.entries`` → ``AbbrDef`` records."""

from __future__ import annotations

from texsmith.passes.glossary import STRUCTURED_KEYS


def _abbreviations(document) -> dict[str, str]:
    assert document.ir is not None
    return {item.key: item.expansion for item in document.ir.abbreviations}


def test_structured_entries_become_abbreviation_definitions(harness) -> None:
    document = harness.load("glossary", "structured")
    out = harness.run("glossary", document)

    assert out is not document
    assert _abbreviations(out) == {
        "NMR": "Nuclear Magnetic Resonance",  # the inline `*[NMR]: …` wins
        "API": "Application Programming Interface",
        "DOI": "Digital Object Identifier",
    }
    # The structured keys no longer look like glossary terms to ``resolve``.
    assert out.ir.front_matter.keys.press.declare.glossary is None
    # The input is untouched.
    assert set(_abbreviations(document)) == {"NMR"}
    assert set(document.ir.front_matter.keys.press.declare.glossary) >= STRUCTURED_KEYS


def test_a_flat_declaration_is_left_to_tmark(harness) -> None:
    document = harness.load("glossary", "flat")
    assert harness.run("glossary", document) is document
