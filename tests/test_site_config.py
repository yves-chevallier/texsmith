"""Reading ``mkdocs.yml`` and ``zensical.toml`` without the generator.

The loader has to survive the tags MkDocs puts in a configuration file
(``!ENV``, ``!relative``, ``!!python/name:``) and its ``INHERIT`` mechanism,
and it must never import what ``!!python/name:`` names.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.site import load_site_config
from texsmith.site.config import (
    WEB_TAGS_DEFAULT,
    language_from_mapping,
    plugin_options,
    snippet_auto_append_from_extensions,
    snippet_base_paths_from_extensions,
    web_options,
    web_tags,
)


REPO_ROOT = Path(__file__).resolve().parents[1]

MKDOCS_YML = """\
site_name: Demo site
docs_dir: sources
site_dir: out
theme:
  name: material
  language: !ENV [TEXSMITH_TEST_LANG, fr]
nav:
  - Home: index.md
  - Guide:
      - guide/index.md
plugins:
  - search
  - texsmith:
      template: book
      build_dir: press
  - awesome-nav
markdown_extensions:
  - abbr
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.snippets:
      check_paths: true
      base_path:
        - !relative $config_dir
        - !relative $docs_dir
exclude_docs: |
  assets/**/*.md
"""

ZENSICAL_TOML = """\
[project]
site_name = "Zensical demo"
docs_dir = "sources"
nav = [{ Home = "index.md" }]
markdown_extensions = [
  "abbr",
  { "pymdownx.snippets" = { base_path = ["includes"] } },
]

[project.theme]
name = "material"
language = "de"

[[project.plugins]]
texsmith = { template = "article" }
"""


def test_mkdocs_yaml_tags_are_data_and_never_imports(tmp_path: Path) -> None:
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(MKDOCS_YML, encoding="utf-8")

    config = load_site_config(config_path)

    assert config.site_name == "Demo site"
    assert config.project_dir == tmp_path.resolve()
    assert config.docs_dir == tmp_path.resolve() / "sources"
    assert config.site_dir == tmp_path.resolve() / "out"
    # ``!ENV [NAME, default]`` falls back to the default when unset.
    assert config.language == "fr"
    assert config.nav == [{"Home": "index.md"}, {"Guide": ["guide/index.md"]}]
    assert config.plugin == {"template": "book", "build_dir": "press"}
    # ``!relative $config_dir`` and ``!relative $docs_dir``, in that order.
    assert config.snippet_base_paths == [
        tmp_path.resolve(),
        tmp_path.resolve() / "sources",
    ]
    assert config.exclude_docs == "assets/**/*.md\n"

    # ``!!python/name:`` keeps the dotted name, as a string, without importing.
    fences = config.raw["markdown_extensions"][1]["pymdownx.superfences"]
    assert fences["custom_fences"][0]["format"] == ("pymdownx.superfences.fence_code_format")


def test_env_tag_reads_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TEXSMITH_TEST_LANG", "it")
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(MKDOCS_YML, encoding="utf-8")

    assert load_site_config(config_path).language == "it"


def test_inherit_merges_the_parent_under_the_child(tmp_path: Path) -> None:
    (tmp_path / "base.yml").write_text(
        "site_name: Base\n"
        "site_language: en\n"
        "plugins:\n"
        "  - texsmith:\n"
        "      template: article\n"
        "      build_dir: press\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text(
        "INHERIT: base.yml\nsite_name: Child\ndocs_dir: pages\n", encoding="utf-8"
    )

    config = load_site_config(config_path)

    assert config.site_name == "Child"
    # Inherited: no theme at all, so ``site_language`` has the last word.
    assert config.language == "en"
    assert config.plugin == {"template": "article", "build_dir": "press"}
    assert config.docs_dir == tmp_path.resolve() / "pages"
    assert "INHERIT" not in config.raw


def test_zensical_toml_keys_live_under_project(tmp_path: Path) -> None:
    config_path = tmp_path / "zensical.toml"
    config_path.write_text(ZENSICAL_TOML, encoding="utf-8")

    config = load_site_config(config_path)

    assert config.site_name == "Zensical demo"
    assert config.language == "de"
    assert config.docs_dir == tmp_path.resolve() / "sources"
    # No ``site_dir`` in the file: the default, next to the configuration.
    assert config.site_dir == tmp_path.resolve() / "site"
    assert config.nav == [{"Home": "index.md"}]
    assert config.plugin == {"template": "article"}
    assert config.snippet_base_paths == [tmp_path.resolve() / "includes"]
    assert config.exclude_docs is None
    assert config.raw["project"]["site_name"] == "Zensical demo"


def test_the_repository_s_own_mkdocs_yml() -> None:
    """The acceptance case: TeXSmith's own site configuration."""
    config = load_site_config(REPO_ROOT / "mkdocs.yml")

    assert config.plugin["template"] == "book"
    assert config.docs_dir.name == "docs"
    assert config.language == "en"
    assert config.snippet_base_paths == [REPO_ROOT]
    assert config.site_name == "TeXSmith"
    assert config.nav is None


def test_language_precedence() -> None:
    assert language_from_mapping({"language": "fr", "locale": "de"}, "en") == "fr"
    assert language_from_mapping({"locale": "de"}, "en") == "de"
    assert language_from_mapping({}, "en") == "en"
    assert language_from_mapping(None, None) is None

    class _Locale:
        language = "pt"

    assert language_from_mapping({"locale": _Locale()}) == "pt"


def test_plugin_options_reads_both_spellings() -> None:
    assert plugin_options(["search", {"texsmith": {"template": "book"}}], "texsmith") == {
        "template": "book"
    }
    # Listed bare, or written as a mapping of plugins.
    assert plugin_options(["texsmith"], "texsmith") == {}
    assert plugin_options({"texsmith": {"template": "book"}}, "texsmith") == {"template": "book"}
    assert plugin_options(["search"], "texsmith") == {}
    assert plugin_options(None, "texsmith") == {}


def test_snippet_base_paths_reads_either_spelling(tmp_path: Path) -> None:
    """The extension list of a file, and the ``mdx_configs`` MkDocs hands out."""

    class _Placeholder:
        """What MkDocs' ``!relative $config_dir`` tag becomes."""

        def __fspath__(self) -> str:
            return str(tmp_path)

    mdx_configs = {"pymdownx.snippets": {"base_path": _Placeholder()}}
    assert snippet_base_paths_from_extensions(mdx_configs, tmp_path) == [tmp_path]

    # A list, with a relative entry read from the project directory.
    mdx_configs = {"pymdownx.snippets": {"base_path": [".", str(tmp_path / "extra")]}}
    assert snippet_base_paths_from_extensions(mdx_configs, tmp_path) == [
        tmp_path,
        tmp_path / "extra",
    ]

    extensions = ["abbr", {"pymdownx.snippets": {"base_path": "includes"}}]
    assert snippet_base_paths_from_extensions(extensions, tmp_path) == [tmp_path / "includes"]


def test_snippet_base_paths_is_empty_when_the_extension_is_not_enabled(tmp_path: Path) -> None:
    assert snippet_base_paths_from_extensions({}, tmp_path) == []
    assert snippet_base_paths_from_extensions(None, tmp_path) == []
    assert snippet_base_paths_from_extensions(["abbr", "attr_list"], tmp_path) == []
    assert (
        snippet_base_paths_from_extensions(
            {"pymdownx.snippets": {"base_path": [object()]}}, tmp_path
        )
        == []
    )


def test_snippet_base_paths_default_to_the_project_directory(tmp_path: Path) -> None:
    """``pymdownx.snippets`` defaults to ``['.']``, the directory a build runs from."""
    assert snippet_base_paths_from_extensions({"pymdownx.snippets": {}}, tmp_path) == [tmp_path]
    assert snippet_base_paths_from_extensions(
        {"pymdownx.snippets": {"check_paths": True}}, tmp_path
    ) == [tmp_path]
    assert snippet_base_paths_from_extensions(["abbr", "pymdownx.snippets"], tmp_path) == [tmp_path]


def test_an_unknown_suffix_is_refused(tmp_path: Path) -> None:
    config_path = tmp_path / "mkdocs.json"
    config_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported site configuration file"):
        load_site_config(config_path)


def test_directory_urls_are_read_and_default_to_the_generators_own_default(
    tmp_path: Path,
) -> None:
    """``texsmith site search`` names a built page the way the index does."""
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text("site_name: Demo\n", encoding="utf-8")
    assert load_site_config(config_path).use_directory_urls is True

    config_path.write_text("site_name: Demo\nuse_directory_urls: false\n", encoding="utf-8")
    assert load_site_config(config_path).use_directory_urls is False


def test_snippet_auto_append_resolves_along_the_base_paths(tmp_path: Path) -> None:
    """``auto_append`` names a file relative to ``base_path``, as the extension does."""
    (tmp_path / "includes").mkdir()
    appended = tmp_path / "includes" / "abbreviations.md"
    appended.write_text("*[POSIX]: Portable Operating System Interface\n", encoding="utf-8")

    found = snippet_auto_append_from_extensions(
        {"pymdownx.snippets": {"auto_append": ["includes/abbreviations.md"]}},
        [tmp_path],
    )

    assert found == [appended]


def test_snippet_auto_append_is_empty_without_the_option(tmp_path: Path) -> None:
    """No option, no extension, or a file no base path holds: nothing to append."""
    assert snippet_auto_append_from_extensions({"pymdownx.snippets": {}}, [tmp_path]) == []
    assert snippet_auto_append_from_extensions(["abbr"], [tmp_path]) == []
    assert (
        snippet_auto_append_from_extensions(
            {"pymdownx.snippets": {"auto_append": ["nowhere.md"]}}, [tmp_path]
        )
        == []
    )


def test_web_options_keep_only_what_the_lowering_accepts() -> None:
    options = {"web": {"sections": " title ", "citations": "inline", "tags": "index"}}

    assert web_options(options) == {"sections": "title", "citations": "inline"}


def test_web_tags_defaults_to_the_index_entries_of_a_page() -> None:
    assert web_tags({}) == WEB_TAGS_DEFAULT
    assert web_tags({"web": {}}) == WEB_TAGS_DEFAULT
    assert web_tags({"web": {"tags": "none"}}) == "none"
    assert web_tags({"web": {"tags": " index "}}) == "index"


def test_an_unknown_web_tags_value_warns_and_keeps_the_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING", logger="texsmith.site"):
        assert web_tags({"web": {"tags": "everything"}}) == WEB_TAGS_DEFAULT

    assert "web.tags" in caplog.text
