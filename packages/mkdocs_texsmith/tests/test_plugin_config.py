"""The plugin's own configuration surface: what MkDocs validates for it.

The options are read by ``texsmith.site.book``; MkDocs is what declares and
validates them, so the two lists have to agree — an option the scheme forgets
is an option a site cannot set, whatever the builder would do with it.
"""

from pathlib import Path

from texsmith.site.book import load_book_settings

from mkdocs_plugin_texsmith.plugin import LatexPlugin


BOOK_OPTIONS = {
    "enabled",
    "build_dir",
    "template",
    "copy_assets",
    "clean_assets",
    "embed_documents",
    "language",
    "bibliography",
    "books",
    "template_overrides",
}
SITE_OPTIONS = {"declare", "web", "inject_markdown_extensions", "css"}


def test_the_scheme_declares_the_options_the_book_and_the_site_read() -> None:
    declared = {name for name, _ in LatexPlugin.config_scheme}

    assert declared == BOOK_OPTIONS | SITE_OPTIONS


def test_the_declared_defaults_are_the_builder_defaults(tmp_path: Path) -> None:
    defaults = {name: option.default for name, option in LatexPlugin.config_scheme}

    settings = load_book_settings(
        defaults, project_dir=tmp_path, build_dir=tmp_path / defaults["build_dir"]
    )

    assert settings.template == "book"
    assert settings.copy_assets is True
    assert settings.embed_documents is False
    assert settings.bibliography == []
    assert settings.template_overrides == {}
    assert settings.latex.clean_assets is True
    assert settings.build_dir == tmp_path / "press"
    assert len(settings.books) == 1
