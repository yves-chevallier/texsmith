"""The site index: front-matter padding, diagnostics and cross-page numbering.

``texsmith.site.index`` is what a site generator drives, MkDocs or Zensical,
so these tests speak only :class:`SitePage` — no generator is imported.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import tmark

from texsmith.core.front_matter import split_front_matter
from texsmith.diagnostics import LoggingEmitter
from texsmith.site import SiteIndex, SitePage
from texsmith.site.index import SPAN_FIELDS, PageRecord, merge_declarations


log = logging.getLogger("texsmith.site.tests")


def _page(path: Path, src_uri: str) -> SitePage:
    return SitePage(src_uri=src_uri, abs_src_path=path)


def _index(tmp_path: Path, **kwargs: object) -> SiteIndex:
    return SiteIndex(project_dir=tmp_path, emitter=LoggingEmitter(logger_obj=log), **kwargs)  # type: ignore[arg-type]


def _record(text: str) -> tuple[PageRecord, str]:
    """The record of a page written as ``text``, and the body it holds."""
    meta, body = split_front_matter(text)
    return (
        PageRecord(src_uri="p.md", abs_src_path=Path("p.md"), meta=meta, lines=text.count("\n")),
        body,
    )


def test_the_padding_puts_the_body_back_on_the_file_s_lines() -> None:
    """``padding`` is what the front matter took, measured against the body."""
    record, body = _record("---\ntitle: Demo\nlang: fr\n---\n# Heading\n")

    assert record.meta == {"title": "Demo", "lang": "fr"}
    assert body == "# Heading\n"
    # Four lines of front matter (``---``, two keys, ``---``): the body starts
    # on line 5, and padding + body puts it back there.
    assert record.padding(body) == 4
    assert ("\n" * record.padding(body) + body).splitlines()[4] == "# Heading"


def test_the_padding_handles_the_shapes_the_splitters_disagree_on() -> None:
    """Blank lines after the close, an empty front matter, CRLF, no header."""
    # MkDocs' ``get_data`` eats the blank lines after ``---``; ours keeps them.
    # The padding is measured against the body at hand, so either one lands on
    # the line the file put it on.
    record, body = _record("---\na: 1\n---\n\n\n# T\n")
    assert record.meta == {"a": 1}
    assert ("\n" * record.padding(body) + body).splitlines()[5] == "# T"
    eaten = body.lstrip("\n")
    assert ("\n" * record.padding(eaten) + eaten).splitlines()[5] == "# T"

    # ``---\n---`` parses to no metadata at all, yet took two lines.
    record, body = _record("---\n---\n# T\n")
    assert record.meta == {}
    assert record.padding(body) == 2
    assert ("\n" * record.padding(body) + body).splitlines()[2] == "# T"

    record, body = _record("---\r\na: 1\r\n---\r\n# T\r\n")
    assert record.meta == {"a": 1}
    assert record.padding(body) == 3

    record, body = _record("# T\n\nBody.\n")
    assert (record.meta, body, record.padding(body)) == ({}, "# T\n\nBody.\n", 0)


def test_a_diagnostic_on_a_padded_body_reports_the_file_s_line(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """The front matter shifts nothing: line 8 of the file is line 8 of the report.

    A generator hands the extension the body alone; the index pads it back to
    the offset the front matter had, so a diagnostic names the file's line.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    page_path = docs / "intro.md"
    page_path.write_text(
        "---\ntitle: Intro\nlang: en\n---\n\n# Intro\n\nSee @fw:nothing.\n",
        encoding="utf-8",
    )

    index = _index(tmp_path)
    page = _page(page_path, "docs/intro.md")
    record, body = _record(page_path.read_text(encoding="utf-8"))
    # Four lines of front matter; the blank line after it belongs to the body.
    assert record.padding(body) == 4

    with caplog.at_level(logging.WARNING):
        lowered = index.lower(page, body)
        assert lowered is not None
        index.report(lowered)

    messages = [record.getMessage() for record in caplog.records]
    assert any("docs/intro.md:8:6: warning ref-unresolved:" in message for message in messages)


def test_lowering_reports_a_diagnostic_with_the_page_path(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """A page's diagnostics are logged as ``path:line:col: severity code: message``."""
    page_path = tmp_path / "docs" / "intro.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text("# Intro\n\nSee @fw:nothing.\n", encoding="utf-8")

    index = _index(tmp_path)
    page = _page(page_path, "docs/intro.md")

    with caplog.at_level(logging.WARNING):
        lowered = index.lower(page, page_path.read_text(encoding="utf-8"))
        assert lowered is not None
        index.report(lowered)

    messages = [record.getMessage() for record in caplog.records]
    assert messages, "Expected the index to log the page's diagnostics"
    # The page path, not the temporary absolute one, and tmark's code.
    assert any("docs/intro.md:3:6: warning ref-unresolved:" in message for message in messages)


def test_every_page_of_a_build_registers_in_one_table(tmp_path: Path) -> None:
    """Two pages of a site take two file ids, so their spans do not collide.

    Each page used to lower against a table of its own and take id 0 in it,
    which made the ``(code, span, message)`` identity of a finding on page two
    equal to the same finding on page one.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    index = _index(tmp_path)

    spans: list[int] = []
    for name in ("first.md", "second.md"):
        path = docs / name
        path.write_text(f"# {name}\n\nSee @fw:nothing.\n", encoding="utf-8")
        lowered = index.lower(_page(path, f"docs/{name}"), path.read_text(encoding="utf-8"))
        assert lowered is not None
        spans.extend(
            record.span.file for record in lowered.diagnostics if record.code == "ref-unresolved"
        )

    assert spans == [0, 1]
    files = index.emitter.sink.files
    # ``files.path()`` holds the page's ``src_uri`` as a ``PurePosixPath``:
    # ``.as_posix()`` is the stable comparison, ``str()`` would be OS-native.
    assert [files.path(index_).as_posix() for index_ in spans] == [
        "docs/first.md",
        "docs/second.md",
    ]


def test_a_page_reaches_a_figure_defined_on_another_page(tmp_path: Path) -> None:
    """The pre-pass chains the numbering, so page B resolves page A's ``@fig:``."""
    docs = tmp_path / "docs"
    docs.mkdir()
    first = docs / "first.md"
    first.write_text(
        "# First\n\n![A kitten](kitten.png){#fig:kitten}\n",
        encoding="utf-8",
    )
    second = docs / "second.md"
    second.write_text("# Second\n\nSee @fig:kitten.\n", encoding="utf-8")

    index = _index(tmp_path)
    pages = [_page(first, "first.md"), _page(second, "second.md")]
    index.prepass(pages)

    assert set(index.records) == {"first.md", "second.md"}
    record = index.record("first.md")
    assert record is not None
    assert {label["key"] for label in record.labels} == {"first", "fig:kitten"}

    lowered = index.lower(pages[1], second.read_text(encoding="utf-8"))
    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    # The sibling is a link to the other page, carrying the figure's number.
    assert lowered.text == "# Second\n\nSee [Figure 1](first.md#fig:kitten).\n"


def test_a_page_the_site_never_pre_passed_stays_out_of_the_map(tmp_path: Path) -> None:
    """Lowering a page the pre-pass never saw leaves the site's map alone.

    Zensical publishes what ``exclude_docs`` removes, so such a page is
    lowered like any other; joining the map there would hand its labels to
    the pages rendered after it and to no other — a render order, not a site.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    listed = docs / "listed.md"
    listed.write_text("# Listed\n\n![A kitten](kitten.png){#fig:kitten}\n", encoding="utf-8")
    hidden = docs / "hidden.md"
    hidden.write_text(
        "# Hidden\n\n![A puppy](puppy.png){#fig:puppy}\n\nSee @fig:puppy.\n", encoding="utf-8"
    )

    index = _index(tmp_path)
    index.prepass([_page(listed, "listed.md")])
    before = index.book_for("listed.md")

    lowered = index.lower(_page(hidden, "hidden.md"), hidden.read_text(encoding="utf-8"))

    assert lowered is not None
    # The page reads, with the numbers that follow the site's own.
    assert "See [Figure 2](#fig:puppy)." in lowered.text
    assert set(index.records) == {"listed.md"}
    assert index.book_for("listed.md") == before


def test_a_page_declaring_a_container_kind_lowers_it_to_a_callout(tmp_path: Path) -> None:
    """``press.declare.admonitions`` reaches the parser, so ``::: exercise`` is one.

    The generator hands the body without the front matter; the declarations
    of the page are re-emitted ahead of it, or the parser reports
    ``container-unknown`` and the fence stays literal text on the page.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "ex.md"
    path.write_text(
        "---\n"
        "press:\n"
        "  declare:\n"
        "    admonitions:\n"
        "      exercise: {name: Exercice}\n"
        "---\n"
        "\n"
        "::: exercise\n"
        "Compute it.\n"
        ":::\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/ex.md"), body)

    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    assert lowered.text.strip() == "!!! exercise\n    Compute it."


def test_a_site_wide_declaration_reaches_a_page_with_no_front_matter(tmp_path: Path) -> None:
    """``plugins.texsmith.declare`` declares for every page, including the bare ones."""
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "ex.md"
    path.write_text("::: exercise\nCompute it.\n:::\n", encoding="utf-8")

    index = _index(tmp_path, declare={"admonitions": {"exercise": {"name": "Exercice"}}})
    lowered = index.lower(_page(path, "docs/ex.md"), path.read_text(encoding="utf-8"))

    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    assert lowered.text.strip() == "!!! exercise\n    Compute it."


def test_a_diagnostic_keeps_the_file_s_line_under_a_site_declaration(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """The synthetic header costs the body no line, whatever it weighs.

    It is longer than the four lines of front matter the file carries, so a
    naive header would push every diagnostic down; the spans move back to the
    padded body instead.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "intro.md"
    path.write_text(
        "---\ntitle: Intro\nlang: en\n---\n\n# Intro\n\nSee @fw:nothing.\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    index = _index(
        tmp_path,
        declare={
            "counters": {"ex": {"name": "Exercice", "format": "Exercice {n}"}},
            "admonitions": {"exercise": {"name": "Exercice"}},
        },
    )
    with caplog.at_level(logging.WARNING):
        lowered = index.lower(_page(path, "docs/intro.md"), body)
        assert lowered is not None
        index.report(lowered)

    messages = [record.getMessage() for record in caplog.records]
    assert any("docs/intro.md:8:6: warning ref-unresolved:" in message for message in messages)


def test_a_page_declaration_wins_over_the_site_s(tmp_path: Path) -> None:
    """Both reach the parser; the page's own spelling of a kind is the one used."""
    site = {"counters": {"ex": {"name": "Exercise"}}, "admonitions": {"tip": {"name": "Tip"}}}
    meta = {"title": "T", "press": {"declare": {"counters": {"ex": {"name": "Exercice"}}}}}

    merged = merge_declarations(site, meta)

    assert merged["title"] == "T"
    assert merged["press"]["declare"] == {
        "counters": {"ex": {"name": "Exercice"}},
        "admonitions": {"tip": {"name": "Tip"}},
    }
    # The site's mapping is not the merged one: a second page starts clean.
    assert site["counters"] == {"ex": {"name": "Exercise"}}


def test_the_deprecated_top_level_counters_merge_with_the_site_s(tmp_path: Path) -> None:
    """``counters:`` at the top of a page joins ``press.declare.counters``."""
    merged = merge_declarations(
        {"counters": {"ex": {"name": "Exercice"}}}, {"counters": {"fw": {}}}
    )

    assert "counters" not in merged
    assert merged["press"]["declare"]["counters"] == {"ex": {"name": "Exercice"}, "fw": {}}


def test_span_fields_covers_every_span_of_the_ir_schema() -> None:
    """The shift moves every span there is; a new one in the schema fails here.

    A span the shift misses stays in the synthetic header's coordinates and
    points at the wrong byte of the page — which is how ``key_span`` made a
    reference report the line after its own.
    """
    span_types = {"Span", "SubSpan"}

    def references_a_span(spec: object) -> bool:
        if not isinstance(spec, dict):
            return False
        ref = spec.get("$ref")
        if isinstance(ref, str) and ref.rsplit("/", 1)[-1] in span_types:
            return True
        return any(
            references_a_span(item)
            for key in ("anyOf", "allOf", "oneOf")
            for item in spec.get(key) or ()
        )

    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for name, spec in (node.get("properties") or {}).items():
                if references_a_span(spec):
                    found.add(str(name))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for schema in ("ir", "resolved", "diagnostic"):
        walk(tmark.schema(schema))

    assert found == set(SPAN_FIELDS)


def test_a_fence_include_resolves_against_the_page_then_the_search_path(
    tmp_path: Path,
) -> None:
    """Two directories, two spellings: the page's own, and the project's.

    A site writes a fence's ``include=`` the way ``pymdownx.snippets``
    resolves one — from the ``base_path``, the project directory by default —
    while ``{include}(file)`` means the page's own directory. Both are read,
    the page's first.
    """
    docs = tmp_path / "docs"
    (docs / "guide").mkdir(parents=True)
    (tmp_path / "assets").mkdir()
    (docs / "guide" / "near.c").write_text("int near(void) { return 1; }\n", encoding="utf-8")
    (tmp_path / "assets" / "far.c").write_text("int far(void) { return 2; }\n", encoding="utf-8")
    page = docs / "guide" / "page.md"
    page.write_text(
        '# T\n\n```c include="near.c"\n```\n\n```c include="assets/far.c"\n```\n',
        encoding="utf-8",
    )

    index = _index(tmp_path, include_paths=[tmp_path])
    lowered = index.lower(_page(page, "guide/page.md"), page.read_text(encoding="utf-8"))

    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    assert "int near(void) { return 1; }" in lowered.text
    assert "int far(void) { return 2; }" in lowered.text
    # The attribute is consumed: it is not one Python-Markdown can parse.
    assert "include=" not in lowered.text


def test_a_fence_include_nothing_holds_is_reported(tmp_path: Path) -> None:
    """A path no directory of the search path holds is ``include-missing``."""
    docs = tmp_path / "docs"
    docs.mkdir()
    page = docs / "page.md"
    page.write_text('# T\n\n```c include="nowhere.c"\n```\n', encoding="utf-8")

    index = _index(tmp_path, include_paths=[tmp_path])
    lowered = index.lower(_page(page, "page.md"), page.read_text(encoding="utf-8"))

    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == ["include-missing"]


def test_the_front_matter_epigraph_is_set_under_the_page_s_heading(tmp_path: Path) -> None:
    """``epigraph: {quote, source}`` becomes a blockquote after the opening heading.

    The key is TMark's own, and the lowering is where the site reads it:
    the page kept it in its front matter and showed it nowhere until the
    core learned to print it.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "syntax.md"
    path.write_text(
        "---\n"
        "epigraph:\n"
        "  quote: Tout devrait être rendu aussi simple que possible.\n"
        "  source: Albert Einstein\n"
        "---\n"
        "\n"
        "# Syntaxe\n"
        "\n"
        "Le chapitre.\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/syntax.md"), body)

    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    assert lowered.text.strip() == (
        "# Syntaxe\n"
        "\n"
        '<blockquote class="ts-epigraph">Tout devrait être rendu aussi simple que '
        "possible.<footer>Albert Einstein</footer></blockquote>\n"
        "\n"
        "Le chapitre."
    )


def test_the_epigraph_clears_the_underline_of_a_setext_heading(tmp_path: Path) -> None:
    """A heading written with ``===`` is two lines, and the quote follows both.

    Splicing between the title and its underline would leave the page a
    paragraph followed by a row of equals signs.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "setext.md"
    path.write_text(
        "---\nepigraph:\n  quote: Sous le titre.\n---\n\nSyntaxe\n=======\n\nLe chapitre.\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/setext.md"), body)

    assert lowered is not None
    assert lowered.text.strip() == (
        "Syntaxe\n"
        "=======\n"
        "\n"
        '<blockquote class="ts-epigraph">Sous le titre.</blockquote>\n'
        "\n"
        "Le chapitre."
    )


def test_an_anchor_before_the_heading_keeps_the_epigraph_under_the_title(
    tmp_path: Path,
) -> None:
    """``[]{#numeration}`` on its own line prints nothing: the title still wins.

    The C course names a chapter before its heading so the links that point
    at it have a target; the anchor lowers to ``[](){#numeration}`` and the
    quote goes under the ``# heading`` that follows it, not above the page.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "data.md"
    path.write_text(
        "---\nepigraph:\n  quote: Les données.\n---\n\n[]{#numeration}\n\n# Les données\n\nLe chapitre.\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/data.md"), body)

    assert lowered is not None
    assert lowered.text.strip() == (
        "[](){#numeration}\n"
        "\n"
        "# Les données\n"
        "\n"
        '<blockquote class="ts-epigraph">Les données.</blockquote>\n'
        "\n"
        "Le chapitre."
    )


def test_two_anchors_and_a_comment_are_read_past_to_the_heading(tmp_path: Path) -> None:
    """Several anchors, in one paragraph or in two, and an HTML comment."""
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "anchors.md"
    path.write_text(
        "---\nepigraph:\n  quote: Deux ancres.\n---\n\n"
        "[]{#a} []{#b}\n\n[]{#c}\n\n<!-- une note -->\n\n# Titre\n\nLe chapitre.\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/anchors.md"), body)

    assert lowered is not None
    assert lowered.text.strip() == (
        "[](){#a} [](){#b}\n"
        "\n"
        "[](){#c}\n"
        "\n"
        "<!-- une note -->\n"
        "\n"
        "# Titre\n"
        "\n"
        '<blockquote class="ts-epigraph">Deux ancres.</blockquote>\n'
        "\n"
        "Le chapitre."
    )


def test_an_anchor_with_no_heading_after_it_takes_the_epigraph_at_the_top(
    tmp_path: Path,
) -> None:
    """Nothing the page prints after the anchor: the quote opens the page."""
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "anchor-only.md"
    path.write_text(
        "---\nepigraph:\n  quote: Rien dessous.\n---\n\n[]{#a}\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/anchor-only.md"), body)

    assert lowered is not None
    assert lowered.text.strip() == (
        '<blockquote class="ts-epigraph">Rien dessous.</blockquote>\n\n[](){#a}'
    )


def test_a_page_with_no_heading_takes_its_epigraph_at_the_top(tmp_path: Path) -> None:
    """With nothing to sit under, the epigraph opens the page."""
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "note.md"
    path.write_text(
        "---\nepigraph:\n  quote: Sans titre.\n---\n\nDu texte.\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/note.md"), body)

    assert lowered is not None
    assert lowered.text.strip() == (
        '<blockquote class="ts-epigraph">Sans titre.</blockquote>\n\nDu texte.'
    )


def test_a_callout_inside_a_numbered_one_is_lowered_to_html(tmp_path: Path) -> None:
    """``md_in_html`` cannot read an indented HTML block inside a wrapper.

    A numbered callout takes the ``<div class="admonition …" markdown="1">``
    wrapper; a ``???`` inside it would carry its body four columns in, and
    the ``</div>`` of a ``<div markdown>`` there closes the *wrapper*, which
    swallows the rest of the page. The nested callout takes the wrapper too.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    path = docs / "ex.md"
    path.write_text(
        "---\n"
        "press:\n"
        "  declare:\n"
        "    counters:\n"
        "      ex: {name: Exercice, format: 'Exercice {n}'}\n"
        "    admonitions:\n"
        "      exercise: {counter: ex}\n"
        "---\n"
        "\n"
        "# T\n"
        "\n"
        "::: exercise {#ex:one title=Identificateurs}\n"
        "Lesquels sont valides ?\n"
        "\n"
        "??? solution\n"
        "\n"
        "    La réponse.\n"
        "\n"
        '    <div class="two-column-list" markdown>\n'
        "\n"
        "    1. un\n"
        "\n"
        "    </div>\n"
        ":::\n",
        encoding="utf-8",
    )
    _meta, body = split_front_matter(path.read_text(encoding="utf-8"))

    lowered = _index(tmp_path).lower(_page(path, "docs/ex.md"), body)

    assert lowered is not None
    assert [item.code for item in lowered.diagnostics] == []
    assert '<details class="solution" markdown="1">' in lowered.text
    # The body of the nested callout is at the wrapper's own column.
    assert '\n<div class="two-column-list" markdown>\n' in lowered.text
    assert "\n    <div" not in lowered.text
