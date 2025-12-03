from pathlib import Path

from texsmith.adapters.latex.engines import EngineFeatures

from mkdocs_plugin_texsmith.plugin import LatexPlugin


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
