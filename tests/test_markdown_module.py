from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown


def test_keys_extension_supports_camel_case_sequences() -> None:
    html = render_markdown(
        "Press ++Ctrl+C++ now.",
        extensions=DEFAULT_MARKDOWN_EXTENSIONS,
    ).html

    assert '<span class="keys">' in html
    assert '<kbd class="key-control">Ctrl</kbd>' in html
    assert '<kbd class="key-c">C</kbd>' in html
