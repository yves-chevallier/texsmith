from __future__ import annotations

from bs4 import BeautifulSoup

from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown


def test_zwsp_in_text_is_normalised_to_nbsp() -> None:
    html = render_markdown(
        "before​after",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    soup = BeautifulSoup(html, "html.parser")

    assert "​" not in soup.get_text()
    assert soup.get_text().strip() == "before after"


def test_zero_width_family_is_normalised() -> None:
    html = render_markdown(
        "a​b‌c‍d﻿e",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text().strip()
    for invisible in ("​", "‌", "‍", "﻿"):
        assert invisible not in text
    assert text == "a b c d e"


def test_invisible_chars_skip_code() -> None:
    html = render_markdown("`a​b`", extensions=DEFAULT_MARKDOWN_EXTENSIONS).html
    soup = BeautifulSoup(html, "html.parser")
    code = soup.find("code")
    assert code is not None
    assert code.text == "a​b"
