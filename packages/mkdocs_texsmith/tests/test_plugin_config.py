from pathlib import Path

from texsmith.adapters.latex.engines import EngineFeatures

from mkdocs_plugin_texsmith.plugin import LatexPlugin, _snippet_base_paths


def test_build_latex_config_defaults(tmp_path: Path) -> None:
    plugin = LatexPlugin()
    plugin.config = {"build_dir": "press", "save_html": True, "clean_assets": False}
    plugin._project_dir = tmp_path
    plugin._build_root = tmp_path / "press"

    cfg = plugin._build_latex_config(language="fr-FR")

    assert cfg.language == "fr-FR"
    assert cfg.build_dir == tmp_path / "press"
    assert cfg.clean_assets is False
    assert len(cfg.books) == 1


def test_inline_bibliography_source_path_slugifies() -> None:
    plugin = LatexPlugin()

    assert (
        plugin._inline_bibliography_source_path("My Label").name
        == "frontmatter-my-label.bib"
    )
    assert (
        plugin._inline_bibliography_source_path("  ").name
        == "frontmatter-frontmatter.bib"
    )


def test_coerce_paths_relative_to_project(tmp_path: Path) -> None:
    plugin = LatexPlugin()
    plugin._project_dir = tmp_path

    rel = plugin._coerce_paths(["foo/bar.bib"])
    assert rel == [tmp_path.joinpath("foo/bar.bib").resolve()]

    absolute = Path("/tmp/example.bib")
    paths = plugin._coerce_paths([absolute])
    assert paths == [absolute]


def test_env_flag_enabled_truthy_and_falsey() -> None:
    plugin = LatexPlugin()

    assert plugin._env_flag_enabled("1") is True
    assert plugin._env_flag_enabled("true") is True
    assert plugin._env_flag_enabled("off") is False
    assert plugin._env_flag_enabled(None) is False


def test_ensure_latexmkrc_created(tmp_path: Path) -> None:
    plugin = LatexPlugin()
    tex_path = tmp_path / "book.tex"
    tex_path.write_text("", encoding="utf-8")
    features = EngineFeatures(
        requires_shell_escape=False,
        bibliography=False,
        has_index=False,
        has_glossary=False,
    )

    rc_path = plugin._ensure_latexmkrc(
        tex_path=tex_path, engine="lualatex", features=features
    )

    assert rc_path is not None and rc_path.exists()
    content = rc_path.read_text(encoding="utf-8")
    assert "lualatex" in content
    assert "book" in content


class _FakeConfig:
    """The two attributes ``_snippet_base_paths`` reads off an ``MkDocsConfig``."""

    def __init__(self, mdx_configs: object, config_file_path: str) -> None:
        self.mdx_configs = mdx_configs
        self.config_file_path = config_file_path


def test_snippet_base_paths_reads_the_extension_config(tmp_path: Path) -> None:
    config_file = tmp_path / "mkdocs.yml"

    class _Placeholder:
        """What MkDocs' ``!relative $config_dir`` tag becomes."""

        def __fspath__(self) -> str:
            return str(tmp_path)

    config = _FakeConfig(
        {"pymdownx.snippets": {"base_path": _Placeholder()}}, str(config_file)
    )
    assert _snippet_base_paths(config) == [tmp_path]

    # A list, with a relative entry read from the directory of ``mkdocs.yml``.
    config = _FakeConfig(
        {"pymdownx.snippets": {"base_path": [".", str(tmp_path / "extra")]}},
        str(config_file),
    )
    assert _snippet_base_paths(config) == [tmp_path, tmp_path / "extra"]


def test_snippet_base_paths_is_empty_when_it_cannot_see_one(tmp_path: Path) -> None:
    config_file = str(tmp_path / "mkdocs.yml")
    assert _snippet_base_paths(_FakeConfig({}, config_file)) == []
    assert _snippet_base_paths(_FakeConfig(None, config_file)) == []
    assert (
        _snippet_base_paths(_FakeConfig({"pymdownx.snippets": {}}, config_file)) == []
    )
    assert (
        _snippet_base_paths(
            _FakeConfig({"pymdownx.snippets": {"base_path": [object()]}}, config_file)
        )
        == []
    )
