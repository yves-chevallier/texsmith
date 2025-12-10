from __future__ import annotations

from texsmith.fonts.html_scripts import wrap_scripts_in_html


def test_combining_marks_stick_to_base_script() -> None:
    html = "<p>ܛܘܒܝܗܘܢ ܠܡܣܟܢ̈</p>"
    wrapped, usage, _summary = wrap_scripts_in_html(html)

    assert 'data-script="diacritics"' not in wrapped
    assert 'data-script="syriacfull"' in wrapped
    slugs = {entry.get("slug") for entry in usage}
    assert "syriacfull" in slugs
    # Summary still records diacritics coverage, but rendered markup must not split it.
    assert wrapped.count("data-script=") == 1
