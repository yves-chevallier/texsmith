"""The render command's flags, and what they imply about each other."""

from __future__ import annotations

from pathlib import Path

import pytest

from texsmith.ui.cli.plan import RenderOptionError, resolve_render_plan


def plan(**overrides: object):
    """A plan for the defaults, with ``overrides`` applied."""
    base: dict[str, object] = {
        "front_matter": None,
        "template": None,
        "build_pdf": False,
        "output": None,
        "output_format": "latex",
        "print_context": False,
        "has_attributes": False,
        "no_title": False,
        "strip_heading": False,
        "no_promote_title": False,
        "no_promote_defaulted": True,
        "base_level": "0",
        "base_level_defaulted": True,
        "classic_output": False,
        "open_log": False,
        "make_deps": False,
        "strict": False,
        "deprecated": None,
        "template_options": None,
    }
    base.update(overrides)
    return resolve_render_plan(**base)  # type: ignore[arg-type]


class TestTemplate:
    def test_build_names_a_template(self) -> None:
        assert plan(build_pdf=True).template == "article"

    def test_a_pdf_output_path_implies_a_build_and_says_so(self) -> None:
        result = plan(output=Path("out.pdf"))
        assert result.build_pdf is True
        assert result.template == "article"
        assert result.notices == ("Enabling --build to produce PDF output.",)

    def test_an_explicit_template_is_kept(self) -> None:
        assert plan(build_pdf=True, template="book").template == "book"

    def test_template_selected_follows_the_template(self) -> None:
        """It is derived, so the two cannot disagree."""
        assert plan().template_selected is False
        assert plan(build_pdf=True).template_selected is True

    def test_print_context_never_builds(self) -> None:
        result = plan(print_context=True, build_pdf=True, template="book")
        assert result.build_pdf is False

    def test_typst_takes_a_template_from_build_but_not_from_the_output_path(self) -> None:
        """An asymmetry of the command as it stands, pinned so a change is deliberate.

        ``--build`` names ``article`` for either backend; a build *inferred*
        from ``-o out.pdf`` names one only for LaTeX, because Typst brings its
        own scaffolding. Unifying the two changes what
        ``--format typst -o out.pdf`` renders, so it needs its own change.
        """
        assert plan(build_pdf=True, output_format="typst").template == "article"
        assert plan(output=Path("out.pdf"), output_format="typst").template is None


class TestAttributes:
    def test_an_attribute_needs_a_template(self) -> None:
        with pytest.raises(RenderOptionError, match="--attribute"):
            plan(has_attributes=True)

    def test_an_explicit_template_allows_them(self) -> None:
        assert plan(has_attributes=True, template="book").template == "book"

    def test_the_template_build_implies_counts(self) -> None:
        assert plan(has_attributes=True, build_pdf=True).template == "article"

    def test_a_template_inferred_from_the_output_path_comes_too_late(self) -> None:
        """The guard is judged before ``-o x.pdf`` can imply a build."""
        with pytest.raises(RenderOptionError, match="--attribute"):
            plan(has_attributes=True, output=Path("out.pdf"))


class TestTitle:
    def test_promoted_with_a_template(self) -> None:
        assert plan(template="book").promote_title is True

    def test_not_promoted_without_one(self) -> None:
        """A bare fragment has no title block to fill."""
        assert plan().promote_title is False

    def test_asked_for_explicitly_without_a_template(self) -> None:
        assert plan(no_promote_defaulted=False).promote_title is True

    @pytest.mark.parametrize("flag", ["no_title", "strip_heading"])
    def test_either_flag_stops_the_promotion(self, flag: str) -> None:
        assert plan(template="book", **{flag: True}).promote_title is False


class TestBaseLevel:
    def test_a_fragment_starts_at_section(self) -> None:
        """It is pasted into someone else's document."""
        assert plan().base_level == plan(base_level="section").base_level

    def test_a_template_keeps_the_declared_default(self) -> None:
        assert plan(template="book").base_level == 0

    def test_an_explicit_level_survives_either_way(self) -> None:
        assert (
            plan(base_level="chapter", base_level_defaulted=False).base_level
            == plan(template="book", base_level="chapter", base_level_defaulted=False).base_level
        )

    def test_an_unknown_level_is_reported(self) -> None:
        with pytest.raises(RenderOptionError):
            plan(base_level="stanza", base_level_defaulted=False)


class TestBuildOnlyFlags:
    @pytest.mark.parametrize(
        ("field", "flag"),
        [
            ("classic_output", "--classic-output"),
            ("open_log", "--open-log"),
            ("make_deps", "--makefile-deps"),
        ],
    )
    def test_each_needs_build(self, field: str, flag: str) -> None:
        with pytest.raises(RenderOptionError, match=flag):
            plan(**{field: True})
        assert plan(build_pdf=True, **{field: True}) is not None

    def test_print_context_needs_a_template(self) -> None:
        with pytest.raises(RenderOptionError, match="--print-context"):
            plan(print_context=True)


class TestFrontMatter:
    def test_the_document_can_ask_for_strict(self) -> None:
        assert plan(front_matter={"press": {"features": {"strict": True}}}).strict is True

    def test_the_document_can_set_the_deprecated_level(self) -> None:
        front = {"press": {"diagnostics": {"deprecated": "off"}}}
        assert plan(front_matter=front).deprecated == "off"
        assert plan(front_matter=front, deprecated="info").deprecated == "info"

    def test_numbering_comes_from_the_front_matter_then_the_attributes(self) -> None:
        assert plan(front_matter={"numbered": False}).numbered is False
        assert (
            plan(
                front_matter={"numbered": False},
                template="book",
                has_attributes=True,
                template_options={"numbered": True},
            ).numbered
            is True
        )


def test_a_ci_runner_falls_back_to_classic_output() -> None:
    """There is no terminal to stream latexmk into."""
    assert plan(build_pdf=False, output=Path("o.pdf"), ci_runner=True).classic_output is True
    assert plan(build_pdf=False, output=Path("o.pdf"), ci_runner=False).classic_output is False
