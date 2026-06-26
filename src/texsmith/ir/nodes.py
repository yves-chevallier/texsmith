r"""TeXSmith intermediate representation — sealed ``Block`` / ``Inline`` tree.

This module is the **single source of truth for the shape of a document** once
it has been read from any input format (today: HTML produced by Markdown +
Material/pymdownx). Readers lower their input *into* this tree; writers consume
it to emit LaTeX, Typst, … The IR is **semantic and backend-agnostic**: a table
carries the validated :mod:`texsmith.extensions.tables` model (one-letter
semantic alignment ``l``/``c``/``r``/``j``), never a LaTeX preamble letter or a
column spec like ``"lrX"``. Computing a backend preamble is the writer's job.

Design rules (non-negotiable, see ``refactoring/PLAN.md`` Phase 1):

* **No backend strings in the tree.** The only escape hatches are the explicit
  :class:`RawInline` / :class:`RawBlock` nodes, which name their ``format``
  (``"latex"``, ``"typst"``, …). A writer ignores raw nodes whose format is not
  its own.
* **Pure tree, no side state.** Cross-cutting accumulators (citations,
  acronyms, footnote bodies, counters, index, ``requires_shell_escape``,
  pygments styles, …) do **not** live in the IR. They are derived by the writer
  while walking the tree and stored in a backend-side ``WriterState`` (Phase 3).
  See the "Transverse state map" section below.
* **Immutable, structural equality.** Every node is a ``frozen``, ``slots``
  dataclass. Sequences of children are stored as ``tuple`` so nodes are
  hashable and compare by value. This makes ``walk`` / ``map`` and golden
  comparisons reliable.

------------------------------------------------------------------------------
Typed node vs. generic ``Div`` / ``Span``
------------------------------------------------------------------------------

A concept earns a **typed node** when it is *stable, tested, and carries
structured fields a writer must reason about*. Everything else is a generic
:class:`Div` (block) or :class:`Span` (inline) carrying free-form ``attrs`` —
this keeps the type count bounded (YAGNI) while staying lossless.

Typed (first-class) — justification:

* :class:`Admonition`  — callouts have a ``kind`` + ``title`` every backend
  maps to a distinct environment; heavily tested (note/warning/details/…).
* :class:`Table`       — wraps the *already-semantic* ``extensions.tables``
  model (multirow/multicolumn, grouped headers, separators). Re-modelling it as
  dataclasses would duplicate ~870 validated lines and break SSOT, so the IR
  node *holds* that model rather than copying it.
* :class:`MarginNote`  — side (left/right) is a structured choice.
* :class:`IndexEntry`  — hierarchical path + style is structured and feeds a
  backend index facility.
* :class:`TexLogo`     — a closed, named set of logos (tex/latex/latex2e).
* :class:`ProgressBar` — a numeric fraction + label, distinct geometry.
* :class:`Keystroke`   — an ordered list of key tokens; tested, structured.

Generic (``Div`` / ``Span`` + ``attrs``) — justification: lead-in paragraphs,
grid-cards, tabbed sets, multi-column lists, ``data-script`` font wrappers,
unicode/regex helper links, and any future Material construct. None of these
need a writer to branch on a dedicated *type*; they are containers with a class
hint. Typing them would explode the surface for no semantic gain.

------------------------------------------------------------------------------
Transverse state map (lives in the *writer*, NOT in the IR)
------------------------------------------------------------------------------

The current pipeline accumulates the following in
``core.context.DocumentState``. None of it belongs in the tree; each entry
below records where it is *derived from* in the IR and where it will be *stored*
in the LaTeX ``WriterState`` (Phase 3):

============================  ===========================  =========================
DocumentState field           Derived from IR node         WriterState home
============================  ===========================  =========================
citations / _citation_index   :class:`Cite`.keys           citation registry (ordered)
bibliography                  (front matter / reader)      bibliography database
abbreviations / acronyms /    (front matter / reader) +    glossary registry
acronym_keys / glossary /     :class:`Span` ``abbr``
acronym_*groups
footnotes                     :class:`Note`.content        footnote registry
index_entries /               :class:`IndexEntry`          index registry
has_index_entries
counters / exercise_counter   (writer-internal)            counter table
requires_shell_escape         :class:`Code` /              shell-escape flag
                              :class:`CodeBlock` engine
pygments_styles               :class:`CodeBlock`.lang      style registry
fallback_summary              :class:`Str`.text scan       font fallback report
headings                      :class:`Header`              TOC builder
script_usage                  :class:`Span`/:class:`Div`   ``data-script`` tracker
                              ``script`` attr
callouts_used                 :class:`Admonition`          callout flag
snippets / solutions          (reader, pre-IR)             n/a (resolved upstream)
============================  ===========================  =========================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from texsmith.extensions.tables.schema import Table as TableModel

# Grouped conceptually: enums, bases, inline nodes, block nodes. (Sorted to
# satisfy RUF022; the categories are documented in the class docstrings.)
__all__ = [
    "Admonition",
    "AnyNode",
    "Block",
    "BlockQuote",
    "BulletList",
    "Cite",
    "Code",
    "CodeBlock",
    "DefinitionItem",
    "DefinitionList",
    "Div",
    "Document",
    "Emph",
    "Figure",
    "Header",
    "Highlight",
    "HorizontalRule",
    "Image",
    "IndexEntry",
    "Inline",
    "Keystroke",
    "LineBreak",
    "Link",
    "ListStyle",
    "MarginNote",
    "MarginSide",
    "Math",
    "Node",
    "Note",
    "OrderedList",
    "Para",
    "Plain",
    "ProgressBar",
    "Quoted",
    "RawBlock",
    "RawInline",
    "SmallCaps",
    "SoftBreak",
    "Space",
    "Span",
    "Str",
    "Strikeout",
    "Strong",
    "Subscript",
    "Superscript",
    "Table",
    "TexLogo",
    "Underline",
]


# ---------------------------------------------------------------------------
# Semantic enumerations
# ---------------------------------------------------------------------------


class ListStyle(Enum):
    """Numbering style of an :class:`OrderedList`."""

    DECIMAL = "decimal"
    LOWER_ALPHA = "lower-alpha"
    UPPER_ALPHA = "upper-alpha"
    LOWER_ROMAN = "lower-roman"
    UPPER_ROMAN = "upper-roman"


class MarginSide(Enum):
    """Which margin a :class:`MarginNote` is placed in."""

    LEFT = "left"
    RIGHT = "right"


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Node:
    """Root of the sealed IR hierarchy. Never instantiated directly."""


@dataclass(frozen=True, slots=True)
class Inline(Node):
    """Marker base for inline-level (phrasing) nodes."""


@dataclass(frozen=True, slots=True)
class Block(Node):
    """Marker base for block-level nodes."""


# ---------------------------------------------------------------------------
# Inline nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Str(Inline):
    """A run of literal text. Backends escape it; the IR keeps it raw."""

    text: str


@dataclass(frozen=True, slots=True)
class Space(Inline):
    """Inter-word space."""


@dataclass(frozen=True, slots=True)
class SoftBreak(Inline):
    """A source line break that does not force a line break in output."""


@dataclass(frozen=True, slots=True)
class LineBreak(Inline):
    """A hard line break (``<br>``)."""


@dataclass(frozen=True, slots=True)
class Emph(Inline):
    """Emphasis (``<em>``)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Strong(Inline):
    """Strong emphasis (``<strong>``)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Strikeout(Inline):
    """Struck-through text (``<del>``)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Underline(Inline):
    """Underlined text (``<ins>``)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Highlight(Inline):
    """Highlighted / marked text (``<mark>``)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Subscript(Inline):
    """Subscript text (``<sub>``)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Superscript(Inline):
    """Superscript text (``<sup>``, not a footnote ref)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class SmallCaps(Inline):
    """Small-capitals text."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Quoted(Inline):
    """Inline quotation (``<q>``); backend chooses the quote glyphs."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Code(Inline):
    """Inline code span. ``lang`` is empty for plain monospace."""

    text: str
    lang: str = ""


@dataclass(frozen=True, slots=True)
class Math(Inline):
    """Math. ``display=True`` is a displayed equation, else inline.

    ``text`` is the raw TeX-flavoured math source (the lingua franca of math
    across backends); it is *not* escaped.
    """

    text: str
    display: bool = False


@dataclass(frozen=True, slots=True)
class Link(Inline):
    """Hyperlink or cross-reference.

    ``target`` is a URL (``https://…``) or an internal identifier (``#anchor``
    or a bare label). Writers decide between ``\\href`` and ``\\ref`` based on
    the target shape; the IR does not pre-classify it.
    """

    content: tuple[Inline, ...]
    target: str
    title: str = ""


@dataclass(frozen=True, slots=True)
class Cite(Inline):
    """Bibliographic citation. The writer collects ``keys`` into its state."""

    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Note(Inline):
    """Footnote, Pandoc-style: the body travels *with* the reference.

    The writer hoists the body and assigns a number; the IR keeps the content
    inline so the tree stays self-contained.
    """

    content: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class Image(Inline):
    """An inline image reference.

    A block-level / captioned image is a :class:`Figure` wrapping this node.
    ``src`` is a path or URL; the writer resolves and hashes assets.
    """

    src: str
    alt: tuple[Inline, ...] = ()
    title: str = ""
    width: str = ""


@dataclass(frozen=True, slots=True)
class IndexEntry(Inline):
    """Index marker. ``path`` is the hierarchical entry (``a!b!c`` in LaTeX).

    ``style`` applies to the deepest term (``"b"`` bold, ``"i"`` italic,
    ``"bi"`` both, or ``""``). ``visible`` content is rendered in place (empty
    for an invisible marker). The writer owns the index registry.
    """

    path: tuple[str, ...]
    style: str = ""
    registry: str = ""
    visible: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class TexLogo(Inline):
    """A named logo from a closed set (``tex`` / ``latex`` / ``latex2e``)."""

    name: str


@dataclass(frozen=True, slots=True)
class Keystroke(Inline):
    """Keyboard shortcut as an ordered sequence of key tokens (``ctrl``, ``s``)."""

    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarginNote(Inline):
    """Margin/side note. ``side`` selects the margin."""

    content: tuple[Block, ...]
    side: MarginSide = MarginSide.RIGHT


@dataclass(frozen=True, slots=True)
class Span(Inline):
    """Generic inline container with free-form attributes (Pandoc ``Span``).

    The escape valve for inline constructs that do not warrant a typed node:
    ``data-script`` font wrappers, abbreviations (``abbr`` + expansion),
    unicode/regex helper links, critic comments, etc. ``attrs`` carries the
    semantic hints (e.g. ``{"role": "abbr", "title": "…"}``); writers branch on
    them, but the IR stays generic.
    """

    content: tuple[Inline, ...]
    attrs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RawInline(Inline):
    """Backend-specific inline passthrough. Ignored by non-matching writers."""

    format: str
    text: str


# ---------------------------------------------------------------------------
# Block nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Para(Block):
    """A paragraph."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Plain(Block):
    """Inline content with no enclosing paragraph (e.g. a tight list item)."""

    content: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Header(Block):
    """A section heading. ``level`` is 1..6; ``numbered`` drives the backend."""

    level: int
    content: tuple[Inline, ...]
    identifier: str = ""
    numbered: bool = True


@dataclass(frozen=True, slots=True)
class CodeBlock(Block):
    """A fenced code block.

    ``highlight`` lists 1-based line numbers to emphasise. ``filename`` labels
    the block. The writer derives ``requires_shell_escape`` / pygments styles.
    """

    text: str
    lang: str = ""
    highlight: tuple[int, ...] = ()
    lineno: bool = False
    filename: str = ""


@dataclass(frozen=True, slots=True)
class BlockQuote(Block):
    """A block quotation (a plain ``<blockquote>``; callouts are admonitions)."""

    content: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class BulletList(Block):
    """An unordered list. Each item is a sequence of blocks."""

    items: tuple[tuple[Block, ...], ...]


@dataclass(frozen=True, slots=True)
class OrderedList(Block):
    """An ordered list with a starting number and numbering style."""

    items: tuple[tuple[Block, ...], ...]
    start: int = 1
    style: ListStyle = ListStyle.DECIMAL


@dataclass(frozen=True, slots=True)
class DefinitionItem(Node):
    """One term plus its definitions in a :class:`DefinitionList`."""

    term: tuple[Inline, ...]
    definitions: tuple[tuple[Block, ...], ...]


@dataclass(frozen=True, slots=True)
class DefinitionList(Block):
    """A description list (``<dl>``)."""

    items: tuple[DefinitionItem, ...]


@dataclass(frozen=True, slots=True)
class HorizontalRule(Block):
    """A thematic break (``<hr>``)."""


@dataclass(frozen=True, slots=True)
class Table(Block):
    """A table.

    The IR delegates the heavy structural model (grouped headers, multirow /
    multicolumn spans, separators, alignment, width) to the validated,
    *already-semantic* :class:`texsmith.extensions.tables.schema.Table`. That
    model is the SSOT for table **shape**; re-implementing it here would
    duplicate ~870 lines and diverge. Alignment in that model is the one-letter
    semantic form (``l``/``c``/``r``/``j``). **No LaTeX preamble string lives
    in it.**

    ``caption`` and ``label`` are lifted to the IR so they carry inline content
    and an identifier independently of the structural model.

    Rich cell content (``cells``)
    --------------------------------------------------------------------------
    The embedded ``model``'s cells stay *scalar* (the schema only models shape:
    spans, separators, column structure). The **rendered inline content** of
    every cell — bold, inline code, links, smart quotes, escaped specials — is
    carried separately in :attr:`cells`, a flat tuple of inline runs in **HTML
    document order**: the exact order
    :func:`texsmith.extensions.tables.html.render_table_html` emits the
    ``<th>`` / ``<td>`` elements (caption excluded). That order is, per row:

    * all header cells, level by level (``_header_matrix`` order: a group name
      before its sub-columns);
    * then, for each body / footer row, the row-label cell followed by its
      data cells at their *origin* positions (absorbed multirow / multicolumn
      slots are **not** present, matching the HTML);
    * separator rows contribute **no** entry (their optional label is plain
      text and stays scalar on ``model`` as ``Separator.label``).

    A writer reproduces both legacy paths by walking ``cells`` in lockstep with
    the cells it already iterates: the yaml path walks the ``<th>`` / ``<td>``
    of ``render_table_html(model)`` (same document order); the plain-GFM path
    walks the leaf columns then, per row, ``[label, *DataRow.cells]`` — which is
    the *same* order, since a plain table has no groups, spans or labelled
    separators. ``cells`` is empty only for the degenerate fallback (never an
    ``ir.Table``). Each entry is a ``tuple[Inline, ...]`` (possibly empty for a
    blank cell) ready for the normal inline-emission path.

    Layout presentation (``env`` / ``colspec`` / ``width`` / ``placement``)
    --------------------------------------------------------------------------
    These four fields are the **precomputed layout directive** for a *rich*
    (``yaml table`` / ``yaml table-config``) table, lifted verbatim from the
    table extension's ``data-ts-*`` attributes (the very output of
    :func:`texsmith.extensions.tables.layout.compute_layout`). They are a
    *documented, scoped escape hatch* for table presentation — the table
    extension's own format, not a generic LaTeX backend string — kept because
    per-column widths and column-group preamble wrappers are **not recoverable**
    from the flattened ``<th>/<td>`` text once the extension has rendered them
    to HTML, so re-deriving them lossily from cell text would break parity.

    Contract for writers:

    * ``env == ""`` → **plain GFM table** (no ``data-ts-table``). The writer
      renders via the plain ``table.tex`` path purely from ``model``. The other
      three strings are empty and unused.
    * ``env != ""`` → **rich table**. ``env`` is ``"tabular"`` / ``"tabularx"``
      / ``"longtable"``; ``colspec`` is the full LaTeX column preamble (e.g.
      ``>{\\raggedright\\arraybackslash}p{3cm}rX``); ``width`` is the
      ``tabularx`` / ``longtable`` outer width (``""`` for ``tabular``);
      ``placement`` is the float specifier (``"htbp!"`` …, possibly ``""``).
      The writer emits the preamble from these strings directly and assembles
      header / body / footer rows from the *rich* ``model`` (which carries the
      column groups, multirow / multicolumn spans and separators reconstructed
      from the HTML). ``env`` / ``colspec`` / ``width`` / ``placement`` for a
      rich ``model`` are exactly what ``compute_layout(model)`` returns, so a
      writer may either trust these strings or recompute them — both agree.
    """

    model: TableModel
    caption: tuple[Inline, ...] = ()
    label: str = ""
    cells: tuple[tuple[Inline, ...], ...] = ()
    env: str = ""
    colspec: str = ""
    width: str = ""
    placement: str = ""


@dataclass(frozen=True, slots=True)
class Figure(Block):
    """A captioned floating block wrapping its content (image, table, …)."""

    content: tuple[Block, ...]
    caption: tuple[Inline, ...] = ()
    identifier: str = ""
    placement: str = ""


@dataclass(frozen=True, slots=True)
class Admonition(Block):
    """A callout / notice block (note, warning, details, …).

    ``kind`` is the semantic type (``note``/``warning``/…); the writer maps it
    to a backend environment. ``collapsible`` reflects ``<details>`` origin.
    """

    kind: str
    title: tuple[Inline, ...]
    content: tuple[Block, ...]
    collapsible: bool = False


@dataclass(frozen=True, slots=True)
class ProgressBar(Block):
    """A progress bar. ``fraction`` in [0, 1]; ``label`` optional; ``thin`` geometry."""

    fraction: float
    label: tuple[Inline, ...] = ()
    thin: bool = False


@dataclass(frozen=True, slots=True)
class Div(Block):
    """Generic block container with free-form attributes (Pandoc ``Div``).

    The escape valve for block constructs that do not warrant a typed node:
    lead-in paragraphs, grid-cards, tabbed sets, multi-column lists,
    ``data-script`` paragraph groups, etc. ``attrs`` carries the semantic hint
    (e.g. ``{"role": "multicolumn", "columns": "2"}``).
    """

    content: tuple[Block, ...]
    attrs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RawBlock(Block):
    """Backend-specific block passthrough. Ignored by non-matching writers."""

    format: str
    text: str


# ---------------------------------------------------------------------------
# Document root
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Document(Block):
    """The whole document: an ordered sequence of top-level blocks.

    A ``Block`` subtype so it traverses uniformly; it is the conventional root
    a reader returns and a writer consumes.
    """

    content: tuple[Block, ...] = field(default_factory=tuple)


# Public union used by the visitor / type guards. ``Document`` is a Block.
AnyNode = Block | Inline | DefinitionItem
