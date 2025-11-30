from __future__ import annotations

from texsmith.fonts.blocks import ScriptTracker, wrap_foreign_scripts


def test_wrap_foreign_scripts_wraps_greek_text():
    tracker = ScriptTracker()
    text = "Hello κόσμε!"
    wrapped = wrap_foreign_scripts(text, tracker=tracker)
    assert "\\textgreek{" in wrapped
    usage = tracker.to_payload()
    assert any(entry["script_id"] == "greek" for entry in usage)
    greek_entry = next(entry for entry in usage if entry["script_id"] == "greek")
    assert greek_entry["count"] == len("κόσμε")
    assert greek_entry["samples"][0].startswith("κόσ")


def test_wrap_foreign_scripts_preserves_emoji():
    tracker = ScriptTracker()
    wrapped = wrap_foreign_scripts("Hi 👋🏽!", tracker=tracker)
    assert wrapped.startswith("Hi")
    assert "\\foreignlanguage" not in wrapped
    assert not tracker.has_usage()
