import pytest

from texsmith.core.templates.manifest import TemplateError
from texsmith.fragments.geometry import GeometryFragment, GeometryFragmentConfig, fragment
from texsmith.fragments.geometry.paper import inject_geometry_context


def test_geometry_fragment_renders_watermark_and_binding() -> None:
    fragment = GeometryFragment(
        {
            "paper": {
                "format": "letter",
                "margin": {"top": "2cm", "left": "10mm"},
                "binding": "0.5in",
                "watermark": "\\LaTeX{}",
            },
            "geometry": {"heightrounded": True},
        }
    )

    rendered = fragment.get_latex()

    assert (
        "\\usepackage[top=20mm,left=10mm,letterpaper,bindingoffset=12.7mm,heightrounded]{geometry}"
        in rendered
    )
    assert "\\geometry" not in rendered
    assert "\\AddToHook{shipout/background}" in rendered
    assert "\\node[rotate=45,scale=7,text opacity=0.06]" in rendered


def test_geometry_fragment_config_coerces_top_level_fields() -> None:
    config = GeometryFragmentConfig.model_validate(
        {"margin": "3cm", "geometry": {"headsep": "0.8in"}, "orientation": "horizontal"}
    )

    resolution = config.resolve()

    assert resolution.paper_option is None
    assert resolution.orientation_option == "landscape"
    assert resolution.geometry_options.startswith("margin=30mm")
    assert "headsep=20.32mm" in resolution.geometry_extra_options


def test_default_a4paper_when_no_front_matter() -> None:
    context: dict[str, object] = {}
    context.update(fragment.context_defaults)
    resolution = inject_geometry_context(context)

    assert "a4paper" in resolution.geometry_options


def test_unit_conversion_with_pint() -> None:
    context = {"paper": {"format": "a4", "margin": "2in"}}
    resolution = inject_geometry_context(context)

    assert "margin=50.8mm" in resolution.geometry_options


def test_invalid_unit_raises() -> None:
    context = {"paper": {"format": "a4", "margin": "10qq"}}

    with pytest.raises(TemplateError):
        inject_geometry_context(context)


def test_orientation_alias_horizontal() -> None:
    context = {"paper": {"format": "a3", "orientation": "horizontal"}}
    resolution = inject_geometry_context(context)

    assert resolution.orientation_option == "landscape"
    assert "landscape" in resolution.geometry_options


def test_watermark_injection_with_tikz() -> None:
    fragment = GeometryFragment({"paper": {"format": "a4", "watermark": "draft"}})
    rendered = fragment.get_latex()

    assert "\\AddToHook{shipout/background}" in rendered
    assert "\\textbf{\\textsf{draft}}" in rendered
