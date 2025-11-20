from pathlib import Path

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

    assert plugin._inline_bibliography_source_path("My Label").name == "frontmatter-my-label.bib"
    assert plugin._inline_bibliography_source_path("  ").name == "frontmatter-frontmatter.bib"


def test_coerce_paths_relative_to_project(tmp_path: Path) -> None:
    plugin = LatexPlugin()
    plugin._project_dir = tmp_path

    rel = plugin._coerce_paths(["foo/bar.bib"])
    assert rel == [tmp_path.joinpath("foo/bar.bib").resolve()]

    absolute = Path("/tmp/example.bib")
    paths = plugin._coerce_paths([absolute])
    assert paths == [absolute]
