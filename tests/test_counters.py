"""Tests for the custom counters feature (``counters:`` front matter).

Three layers are covered:

* :mod:`texsmith.core.counters` — front-matter parsing, the ``CounterSpec``
  format contract and the process-global ``CounterRegistry``;
* the Markdown extension — ``#{prefix:key}`` definitions, ``{#prefix:key}``
  silent definitions, ``@prefix:key`` references and the inertness rules that
  keep Ruby/CoffeeScript interpolations intact;
* the LaTeX and Typst writers — ``\\phantomsection\\label{}`` / ``<label>``
  anchors and their reference sites.

The registry is a singleton shared across conversions, so every test starts
from a cleared registry (autouse fixture below).
"""

from __future__ import annotations

from collections.abc import Iterator
import re
import warnings

from bs4 import BeautifulSoup
import pytest

from texsmith.adapters.latex import LaTeXRenderer
from texsmith.adapters.markdown import DEFAULT_MARKDOWN_EXTENSIONS, render_markdown
from texsmith.core.counters import (
    CounterRegistry,
    CounterSpec,
    CounterValidationError,
    clear_registry,
    get_registry,
    parse_front_matter_counters,
)
from texsmith.readers.html import HtmlReader
from texsmith.writers.typst import TypstWriter, TypstWriterState
from texsmith.writers.typst.writer import citation_label


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clear_counter_registry() -> Iterator[None]:
    """The counter registry is process-global: no numbering may leak between tests."""
    clear_registry()
    yield
    clear_registry()


FRONT_MATTER = """---
counters:
  n:
    name: Requirement
    format: "N-{n:02d}"
---
"""

TWO_COUNTERS_FRONT_MATTER = """---
counters:
  n:
    name: Requirement
    format: "N-{n:02d}"
  fw:
    name: Finding
    format: "FW-{n:02d}"
---
"""


def _html(source: str) -> str:
    return render_markdown(source, extensions=DEFAULT_MARKDOWN_EXTENSIONS).html


def _render(source: str) -> BeautifulSoup:
    return BeautifulSoup(_html(source), "html.parser")


def _counter_texts(soup: BeautifulSoup) -> list[str]:
    return [span.get_text() for span in soup.find_all("span", class_="ts-counter")]


# --------------------------------------------------------------------------- #
# parse_front_matter_counters
# --------------------------------------------------------------------------- #


def test_parse_returns_empty_mapping_when_counters_absent() -> None:
    assert parse_front_matter_counters(None) == {}
    assert parse_front_matter_counters({}) == {}
    assert parse_front_matter_counters({"title": "No counters here"}) == {}


def test_parse_returns_empty_mapping_for_empty_counters_section() -> None:
    assert parse_front_matter_counters({"counters": {}}) == {}
    # ``counters:`` with nothing under it parses to ``None`` in YAML.
    assert parse_front_matter_counters({"counters": None}) == {}


def test_parse_applies_format_and_start_defaults() -> None:
    specs = parse_front_matter_counters({"counters": {"n": {"name": "Requirement"}}})

    assert specs == {"n": CounterSpec(prefix="n", name="Requirement", format="{n}", start=1)}
    assert specs["n"].format == "{n}"
    assert specs["n"].start == 1


def test_parse_keeps_explicit_format_and_start() -> None:
    specs = parse_front_matter_counters(
        {"counters": {"fw": {"name": "Finding", "format": "FW-{n:02d}", "start": 10}}}
    )

    assert specs == {"fw": CounterSpec(prefix="fw", name="Finding", format="FW-{n:02d}", start=10)}


def test_parse_accepts_several_prefixes() -> None:
    specs = parse_front_matter_counters(
        {"counters": {"n": {"name": "Requirement"}, "fw": {"name": "Finding"}}}
    )

    assert sorted(specs) == ["fw", "n"]
    assert specs["fw"].prefix == "fw"


def test_counter_validation_error_is_a_value_error() -> None:
    assert issubclass(CounterValidationError, ValueError)


def test_parse_rejects_reserved_prefix() -> None:
    with pytest.raises(CounterValidationError) as excinfo:
        parse_front_matter_counters({"counters": {"fig": {"name": "Figure"}}})

    assert "fig" in str(excinfo.value)


def test_parse_rejects_invalid_prefix_starting_with_a_digit() -> None:
    with pytest.raises(CounterValidationError) as excinfo:
        parse_front_matter_counters({"counters": {"2n": {"name": "Requirement"}}})

    assert "2n" in str(excinfo.value)


def test_parse_rejects_prefix_containing_a_space() -> None:
    with pytest.raises(CounterValidationError) as excinfo:
        parse_front_matter_counters({"counters": {"a b": {"name": "Requirement"}}})

    assert "a b" in str(excinfo.value)


def test_parse_rejects_unknown_field() -> None:
    with pytest.raises(CounterValidationError) as excinfo:
        parse_front_matter_counters({"counters": {"n": {"name": "Requirement", "colour": "red"}}})

    assert "n" in str(excinfo.value)


def test_parse_rejects_empty_name() -> None:
    with pytest.raises(CounterValidationError):
        parse_front_matter_counters({"counters": {"n": {"name": ""}}})


def test_parse_rejects_missing_name() -> None:
    with pytest.raises(CounterValidationError):
        parse_front_matter_counters({"counters": {"n": {"format": "N-{n}"}}})


def test_parse_rejects_unknown_format_field() -> None:
    with pytest.raises(CounterValidationError) as excinfo:
        parse_front_matter_counters(
            {"counters": {"n": {"name": "Requirement", "format": "{oops}"}}}
        )

    assert "n" in str(excinfo.value)


def test_parse_rejects_unbalanced_format_braces() -> None:
    with pytest.raises(CounterValidationError):
        parse_front_matter_counters({"counters": {"n": {"name": "Requirement", "format": "{n"}}})


def test_parse_rejects_non_integer_start() -> None:
    with pytest.raises(CounterValidationError):
        parse_front_matter_counters({"counters": {"n": {"name": "Requirement", "start": "one"}}})


def test_parse_rejects_counters_that_are_not_a_mapping() -> None:
    with pytest.raises(CounterValidationError):
        parse_front_matter_counters({"counters": ["n", "fw"]})


def test_parse_rejects_entry_that_is_not_a_mapping() -> None:
    with pytest.raises(CounterValidationError) as excinfo:
        parse_front_matter_counters({"counters": {"n": "Requirement"}})

    assert "n" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# CounterSpec.render
# --------------------------------------------------------------------------- #


def test_spec_render_default_format_is_the_bare_number() -> None:
    spec = CounterSpec(prefix="n", name="Requirement")
    assert spec.render(7, "joy") == "7"


def test_spec_render_pads_with_format_spec() -> None:
    spec = CounterSpec(prefix="n", name="Requirement", format="N-{n:02d}")
    assert spec.render(1, "joy") == "N-01"
    assert spec.render(42, "joy") == "N-42"
    assert spec.render(123, "joy") == "N-123"


def test_spec_render_exposes_prefix_and_key_fields() -> None:
    spec = CounterSpec(prefix="fw", name="Finding", format="{prefix}/{key}/{n}")
    assert spec.render(3, "boot-loop") == "fw/boot-loop/3"


# --------------------------------------------------------------------------- #
# CounterRegistry
# --------------------------------------------------------------------------- #


def _registry() -> CounterRegistry:
    registry = CounterRegistry()
    registry.declare(
        {
            "n": CounterSpec(prefix="n", name="Requirement", format="N-{n:02d}"),
            "fw": CounterSpec(prefix="fw", name="Finding", format="FW-{n}", start=10),
        }
    )
    return registry


def test_registry_allocates_independent_series_per_prefix() -> None:
    registry = _registry()

    assert registry.allocate("n", "joy") == (1, False)
    assert registry.allocate("fw", "boot") == (10, False)
    assert registry.allocate("n", "respect") == (2, False)
    assert registry.allocate("fw", "reset") == (11, False)


def test_registry_honours_start() -> None:
    registry = CounterRegistry()
    registry.declare({"n": CounterSpec(prefix="n", name="Requirement", start=100)})

    assert registry.allocate("n", "a") == (100, False)
    assert registry.allocate("n", "b") == (101, False)


def test_registry_reallocating_the_same_key_flags_a_duplicate() -> None:
    registry = _registry()

    assert registry.allocate("n", "joy") == (1, False)
    assert registry.allocate("n", "respect") == (2, False)
    # The duplicate keeps the first number and does not consume a new one.
    assert registry.allocate("n", "joy") == (1, True)
    assert registry.allocate("n", "next") == (3, False)


def test_registry_spec_lookup() -> None:
    registry = _registry()

    spec = registry.spec("n")
    assert spec is not None
    assert spec.name == "Requirement"
    assert registry.spec("nope") is None


def test_registry_lookup_and_render_unknown_keys_return_none() -> None:
    registry = _registry()
    registry.allocate("n", "joy")

    assert registry.lookup("n", "joy") == 1
    assert registry.render("n", "joy") == "N-01"
    # Declared prefix, unknown key.
    assert registry.lookup("n", "missing") is None
    assert registry.render("n", "missing") is None
    # Undeclared prefix.
    assert registry.lookup("zz", "joy") is None
    assert registry.render("zz", "joy") is None


def test_registry_allocate_on_undeclared_prefix_raises_key_error() -> None:
    registry = _registry()

    with pytest.raises(KeyError):
        registry.allocate("zz", "joy")


def test_registry_prepare_reserves_a_value_without_claiming_it() -> None:
    registry = CounterRegistry()
    registry.declare({"n": CounterSpec(prefix="n", name="Need", format="N-{n:02d}")})

    reserved = registry.prepare("n", "joy")
    assert reserved == 1
    assert registry.lookup("n", "joy") == 1

    # The definition itself is not a duplicate: the pre-pass only booked the
    # number the marker will print.
    value, is_duplicate = registry.allocate("n", "joy")
    assert (value, is_duplicate) == (1, False)
    assert registry.allocate("n", "joy") == (1, True)


def test_registry_prepare_fixes_the_order_before_allocation() -> None:
    registry = CounterRegistry()
    registry.declare({"n": CounterSpec(prefix="n", name="Need", format="N-{n:02d}")})

    registry.prepare("n", "second")
    registry.prepare("n", "first")

    assert registry.allocate("n", "first") == (2, False)
    assert registry.allocate("n", "second") == (1, False)


def test_registry_prepare_on_undeclared_prefix_raises_key_error() -> None:
    registry = CounterRegistry()
    with pytest.raises(KeyError):
        registry.prepare("n", "joy")


def test_registry_snapshot_reports_allocated_values() -> None:
    registry = _registry()
    registry.allocate("n", "joy")
    registry.allocate("n", "respect")
    registry.allocate("fw", "boot")

    assert registry.snapshot() == {"n": {"joy": 1, "respect": 2}, "fw": {"boot": 10}}


def test_registry_clear_drops_allocated_values() -> None:
    registry = _registry()
    registry.allocate("n", "joy")
    registry.clear()

    assert registry.lookup("n", "joy") is None
    assert all(not values for values in registry.snapshot().values())

    # Re-declaring and re-allocating restarts the series from ``start``.
    registry.declare({"n": CounterSpec(prefix="n", name="Requirement", format="N-{n:02d}")})
    assert registry.allocate("n", "joy") == (1, False)


def test_registry_declare_merges_with_last_one_winning() -> None:
    registry = CounterRegistry()
    registry.declare({"n": CounterSpec(prefix="n", name="Requirement", format="A-{n}")})
    registry.declare({"n": CounterSpec(prefix="n", name="Requirement", format="B-{n}")})

    registry.allocate("n", "joy")
    assert registry.render("n", "joy") == "B-1"


def test_get_registry_returns_the_same_singleton() -> None:
    assert get_registry() is get_registry()


def test_clear_registry_resets_the_singleton() -> None:
    registry = get_registry()
    registry.declare({"n": CounterSpec(prefix="n", name="Requirement")})
    registry.allocate("n", "joy")
    assert registry.lookup("n", "joy") == 1

    clear_registry()

    assert get_registry().lookup("n", "joy") is None


# --------------------------------------------------------------------------- #
# Markdown → HTML: definitions
# --------------------------------------------------------------------------- #


def test_definition_marker_produces_a_counter_span() -> None:
    soup = _render(f"{FRONT_MATTER}\nRequirement #{{n:joy}} says everyone shall be happy.\n")

    span = soup.find("span", class_="ts-counter")
    assert span is not None
    assert span["id"] == "n:joy"
    assert span["data-counter"] == "n"
    assert span["data-key"] == "joy"
    assert span.get_text() == "N-01"
    assert "#{n:joy}" not in soup.get_text()


def test_numbering_follows_document_order_across_a_table() -> None:
    source = f"""{FRONT_MATTER}
| Id | Requirement |
| --- | --- |
| #{{n:joy}} | Everyone shall be happy |
| #{{n:respect}} | Everyone shall respect the others |
"""
    soup = _render(source)

    assert _counter_texts(soup) == ["N-01", "N-02"]
    assert soup.find("span", id="n:joy").get_text() == "N-01"
    assert soup.find("span", id="n:respect").get_text() == "N-02"


def test_multiple_markers_number_each_prefix_independently() -> None:
    source = f"""{TWO_COUNTERS_FRONT_MATTER}
First #{{n:one}}, then #{{fw:alpha}}, then #{{n:two}}, then #{{fw:beta}}.
"""
    soup = _render(source)

    assert _counter_texts(soup) == ["N-01", "FW-01", "N-02", "FW-02"]


def test_marker_works_in_a_list_item_and_a_heading() -> None:
    source = f"""{FRONT_MATTER}
## Item #{{n:head}}

- #{{n:bullet}} a listed requirement
"""
    soup = _render(source)

    heading = soup.find("h2")
    assert heading is not None
    assert heading.find("span", class_="ts-counter").get_text() == "N-01"
    assert soup.find("li").find("span", class_="ts-counter").get_text() == "N-02"


def test_attr_list_id_defines_a_counter_silently() -> None:
    source = f"""{FRONT_MATTER}
## Boot loop {{#n:boot}}

The watchdog issue (@n:boot) is fixed.
"""
    soup = _render(source)

    heading = soup.find("h2")
    assert heading is not None
    assert heading["id"] == "n:boot"
    # Nothing is printed at the definition site.
    assert heading.get_text().strip() == "Boot loop"
    assert soup.find("span", class_="ts-counter") is None
    # …but the reference still resolves.
    assert soup.find("a", href="#n:boot").get_text() == "N-01"


# --------------------------------------------------------------------------- #
# Markdown → HTML: references
# --------------------------------------------------------------------------- #


def test_reference_anchor_carries_the_formatted_number() -> None:
    source = f"""{FRONT_MATTER}
Requirement #{{n:joy}} matters.

Smile in every circumstance (@n:joy).
"""
    soup = _render(source)

    anchor = soup.find("a", href="#n:joy")
    assert anchor is not None
    assert anchor.get_text() == "N-01"


def test_bracketed_reference_form_also_resolves() -> None:
    source = f"""{FRONT_MATTER}
Requirement #{{n:joy}} matters.

See @[n:joy] for details.
"""
    soup = _render(source)

    assert soup.find("a", href="#n:joy").get_text() == "N-01"


def test_forward_reference_resolves_to_a_later_definition() -> None:
    source = f"""{FRONT_MATTER}
The requirement (@n:joy) is stated below.

Requirement #{{n:joy}} says everyone shall be happy.
"""
    soup = _render(source)

    assert soup.find("span", id="n:joy").get_text() == "N-01"
    assert soup.find("a", href="#n:joy").get_text() == "N-01"


def test_reference_prints_the_number_alone() -> None:
    source = f"""{FRONT_MATTER}
Requirement #{{n:joy}} matters. See @n:joy.
"""
    soup = _render(source)

    anchor = soup.find("a", href="#n:joy")
    assert anchor.get_text() == "N-01"
    # The ``name:`` field is diagnostics-only, never printed.
    assert "Requirement N-01" not in anchor.get_text()


# --------------------------------------------------------------------------- #
# Inertness
# --------------------------------------------------------------------------- #


def test_marker_without_a_colon_stays_literal() -> None:
    soup = _render(f"{FRONT_MATTER}\nRuby interpolation #{{name}} is untouched.\n")

    assert soup.find("span", class_="ts-counter") is None
    assert "#{name}" in soup.get_text()


def test_ruby_interpolation_with_a_dotted_name_stays_literal() -> None:
    soup = _render(f"{FRONT_MATTER}\nGreetings, #{{user.name}}!\n")

    assert soup.find("span", class_="ts-counter") is None
    assert "#{user.name}" in soup.get_text()


def test_undeclared_prefix_stays_literal() -> None:
    soup = _render(f"{FRONT_MATTER}\nShell interpolation #{{sh:var}} is untouched.\n")

    assert soup.find("span", class_="ts-counter") is None
    assert "#{sh:var}" in soup.get_text()


def test_marker_is_inert_without_a_counters_section() -> None:
    soup = _render("---\ntitle: Plain\n---\n\nNothing declared, so #{n:joy} stays.\n")

    assert soup.find("span", class_="ts-counter") is None
    assert "#{n:joy}" in soup.get_text()


def test_marker_is_inert_without_any_front_matter() -> None:
    soup = _render("Nothing declared, so #{n:joy} stays.\n")

    assert soup.find("span", class_="ts-counter") is None
    assert "#{n:joy}" in soup.get_text()


def test_escaped_marker_stays_literal() -> None:
    soup = _render(f"{FRONT_MATTER}\nA literal \\#{{n:joy}} stays.\n")

    assert soup.find("span", class_="ts-counter") is None
    assert "#{n:joy}" in soup.get_text()


def test_marker_inside_a_code_span_stays_literal() -> None:
    soup = _render(f"{FRONT_MATTER}\nUse `#{{n:joy}}` to define a requirement.\n")

    code = soup.find("code")
    assert code is not None
    assert code.get_text() == "#{n:joy}"
    assert soup.find("span", class_="ts-counter") is None


def test_marker_inside_a_fenced_block_stays_literal() -> None:
    source = f'{FRONT_MATTER}\n```ruby\nputs "hello #{{n:joy}}"\n```\n'
    soup = _render(source)

    assert soup.find("span", class_="ts-counter") is None
    assert "#{n:joy}" in soup.get_text()


def test_real_heading_is_still_a_heading() -> None:
    soup = _render(f"{FRONT_MATTER}\n# Real heading\n")

    heading = soup.find("h1")
    assert heading is not None
    assert heading.get_text() == "Real heading"
    assert soup.find("span", class_="ts-counter") is None


def test_index_hashtag_syntax_is_untouched() -> None:
    soup = _render(f"{FRONT_MATTER}\nSee #[LaTeX] and #[Alpha] in the index.\n")

    tags = soup.find_all("span", class_="ts-hashtag")
    assert [tag["data-tag"] for tag in tags] == ["LaTeX", "Alpha"]
    assert soup.find("span", class_="ts-counter") is None


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #


def test_duplicate_key_prints_the_first_number_and_warns() -> None:
    source = f"""{FRONT_MATTER}
First #{{n:joy}} and again #{{n:joy}}, then #{{n:respect}}.
"""
    # Authoring defects go through ``warnings`` so they are visible without a
    # verbosity flag, and can be promoted to errors with ``PYTHONWARNINGS``.
    with pytest.warns(UserWarning, match="joy"):
        soup = _render(source)

    assert _counter_texts(soup) == ["N-01", "N-01", "N-02"]


def test_dangling_reference_renders_empty_and_warns() -> None:
    source = f"""{FRONT_MATTER}
Requirement #{{n:joy}} exists but @n:missing does not.
"""
    with pytest.warns(UserWarning, match="missing"):
        soup = _render(source)

    anchor = soup.find("a", href="#n:missing")
    assert anchor is not None
    assert anchor.get_text() == ""


def test_undeclared_prefix_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _render(f"{FRONT_MATTER}\nAn undeclared #{{x:joy}} marker.\n")


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #


LATEX_SOURCE = f"""{FRONT_MATTER}
Requirement #{{n:joy}} says everyone shall be happy.

Smile in every circumstance (@n:joy).
"""


def test_latex_definition_emits_phantomsection_and_label() -> None:
    latex = LaTeXRenderer().render(_html(LATEX_SOURCE))

    assert "\\phantomsection\\label{n:joy}N-01" in latex


def test_latex_reference_emits_hyperref() -> None:
    latex = LaTeXRenderer().render(_html(LATEX_SOURCE))

    assert "\\hyperref[n:joy]{N-01}" in latex


def _typst(html: str) -> str:
    return TypstWriter(TypstWriterState()).write(HtmlReader().read(html))


# The counter id is routed through ``citation_label`` like every other Typst
# label (cf. ``test_typst_writer.test_labelled_table_is_referenceable_figure``),
# so the exact spelling of the label is derived rather than hard-coded.
TYPST_LABEL = citation_label("n:joy")


def test_typst_definition_attaches_a_label_after_the_number() -> None:
    typst = _typst(_html(LATEX_SOURCE))

    assert f"N-01<{TYPST_LABEL}>" in typst


def test_typst_reference_emits_a_link() -> None:
    typst = _typst(_html(LATEX_SOURCE))

    assert f"#link(<{TYPST_LABEL}>)[N-01]" in typst


def test_typst_definition_and_reference_share_one_label() -> None:
    """The two sites must agree or the Typst link does not resolve."""
    typst = _typst(_html(LATEX_SOURCE))

    labels = re.findall(r"<([^<>]+)>", typst)
    assert labels == [TYPST_LABEL, TYPST_LABEL]
    assert f"#link(<{TYPST_LABEL}>)" in typst
