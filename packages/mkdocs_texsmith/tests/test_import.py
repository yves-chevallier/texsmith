def test_plugin_imports() -> None:
    import mkdocs_plugin_texsmith

    assert hasattr(mkdocs_plugin_texsmith, "LatexPlugin")
