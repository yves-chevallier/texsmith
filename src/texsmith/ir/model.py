"""TeXSmith IR models generated from the tmark IR schema. Do not edit.
tmark version: 0.0.0
schema sha256: b72987141242043c940233fc24a594f0e6ed91b15f01b8d7b98c7714360b9c43

Regenerate with ``scripts/gen_ir_models.py`` (``--check`` in CI). Every node is a
frozen, slotted dataclass; ``id`` and ``span`` do not take part in equality or
hashing (tmark rule 3). ``FIELDS`` and ``UNIONS`` drive :mod:`texsmith.ir.codec`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Final, Literal, NamedTuple, TypeAlias


TMARK_VERSION: Final = '0.0.0'
SCHEMA_HASH: Final = 'b72987141242043c940233fc24a594f0e6ed91b15f01b8d7b98c7714360b9c43'

#: A JSON value the schema leaves untyped (front-matter blobs).
JsonValue: TypeAlias = Any


class Missing:
    """Type of :data:`MISSING`: a key absent from the JSON (not ``null``)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Final = Missing()


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """Byte span ``[file, start, end]``, half-open. ``NO_SPAN`` when unknown."""

    file: int = 0
    start: int = 0
    end: int = 0


NO_SPAN: Final = Span()
SubSpan: TypeAlias = Span


class Align(Enum):
    """Horizontal alignment of a column or cell. Spec §Table (`l|c|r|j`). Mirrors Python `Align = Literal["l", "c", "r", "j"]`; the long forms (`left`, `center`, `centre`, `right`, `justify`, `justified`) are accepted by the parser and normalised here (`ALIGN_ALIASES`)."""

    LEFT = 'l'
    CENTER = 'c'
    RIGHT = 'r'
    JUSTIFY = 'j'


class CaptionKind(Enum):
    """Spec §Caption: `Table:`, `Figure:`, `Listing:`."""

    TABLE = 'table'
    FIGURE = 'figure'
    LISTING = 'listing'


class CaptionPosition(Enum):
    """Source position of a caption line relative to its float. Spec §Caption: after is canonical, before is accepted sugar."""

    BEFORE = 'before'
    AFTER = 'after'


class ListStyle(Enum):
    """Numbering style of an ordered list (`pymdownx.fancylists` markers, spec Appendix "PyMdownX compatibility profile")."""

    DECIMAL = 'decimal'
    LOWER_ALPHA = 'lower_alpha'
    UPPER_ALPHA = 'upper_alpha'
    LOWER_ROMAN = 'lower_roman'
    UPPER_ROMAN = 'upper_roman'
    GENERIC = 'generic'


class QuoteKind(Enum):
    """Spec §Inline text: `"x"` or `'x'`."""

    DOUBLE = 'double'
    SINGLE = 'single'


class Scope(Enum):
    """Numbering scope of a counter. Spec §Counters (`scope`)."""

    DOCUMENT = 'document'
    CHAPTER = 'chapter'
    SECTION = 'section'


class Side(Enum):
    """Layout hint of an aside. Spec §Aside."""

    LEFT = 'left'
    RIGHT = 'right'
    OUTER = 'outer'
    INNER = 'inner'


class Task(Enum):
    """Task state of `- [ ]`, `- [x]` and `- [.]` (feature `tasklist.partial`)."""

    OPEN = 'open'
    DONE = 'done'
    PARTIAL = 'partial'


@dataclass(frozen=True, slots=True)
class Record:
    """A supporting structure without identity (list items, cells, front matter)."""


@dataclass(frozen=True, slots=True)
class Node:
    """A block or inline: identity (``id``) and source ``span``, ignored by ``==``."""

    id: int = field(default=0, compare=False, kw_only=True)
    span: Span = field(default=NO_SPAN, compare=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class Block(Node):
    """Spec §Node catalogue, block entries. Serialised with a `type` tag."""


@dataclass(frozen=True, slots=True)
class Column(Record):
    """Spec §Table rung 5: "Grouped headers (recursive `columns:`)". Mirrors Python `Column = LeafColumn | ColumnGroup`."""


@dataclass(frozen=True, slots=True)
class Inline(Node):
    """Spec §Node catalogue, inline entries. Serialised with a `type` tag."""


@dataclass(frozen=True, slots=True)
class Row(Record):
    """Mirrors Python `Row = Separator | DataRow`."""


@dataclass(frozen=True, slots=True)
class Target(Record):
    """Where a link points. Spec §Ref (textual references) and §Includes."""


@dataclass(frozen=True, slots=True)
class Abbr(Inline):
    """A substituted acronym, resolved from `Document::abbreviations`. Spec §Glossary and acronyms."""

    type: ClassVar[Literal["Abbr"]] = "Abbr"
    text: str


@dataclass(frozen=True, slots=True)
class AbbrDef(Record):
    """A `*[HTML]: HyperText Markup Language` definition. Spec §Glossary and acronyms."""

    expansion: str
    key: str
    id: int = field(default=0, compare=False, kw_only=True)
    span: Span = field(default=NO_SPAN, compare=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class AdmonitionDecl(Record):
    """A declared admonition type. Spec §Admonition."""

    counter: str | None = None
    group: str | None = None
    name: str | None = None
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class Anchor(Target):
    """`#id` in this document."""

    type: ClassVar[Literal["Anchor"]] = "Anchor"
    value: str


@dataclass(frozen=True, slots=True)
class Aside(Inline):
    """`{aside}[…]`, `::: aside`. Spec §Aside (the IR name of the spec's `MarginNote`)."""

    type: ClassVar[Literal["Aside"]] = "Aside"
    content: tuple[Block, ...] = ()
    side: Side | None = None


@dataclass(frozen=True, slots=True)
class Attrs(Record):
    """The attribute list of a host element."""

    classes: tuple[str, ...] = ()
    id: str | None = None
    id_span: Span | None = None
    kv: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Author(Record):
    """Spec §Front matter: `authors: [{name, affiliation}]`. A bare string item (`authors: [Ada Lovelace]`) is the name alone (C9: TMark tolerates what TeXSmith accepts)."""

    name: str
    affiliation: str | None = None
    email: str | None = None


@dataclass(frozen=True, slots=True)
class BulletList(Block):
    """`-` list. Spec §BulletList, OrderedList."""

    type: ClassVar[Literal["BulletList"]] = "BulletList"
    items: tuple[ListItem, ...] = ()


@dataclass(frozen=True, slots=True)
class Cell(Record):
    """One slot of the leaf matrix. Mirrors Python `LeafCell` (`value`, `absorbed`, `rows`, `cols`, `align`; `origin` is implied by the position). A cell written as `{value, rows, cols, align}` in the YAML form is Python's `RichCell`; a bare scalar is a cell with the defaults."""

    absorbed: bool = False
    align: Align | None = None
    cols: int = 1
    content: tuple[Inline, ...] = ()
    rows: int = 1


@dataclass(frozen=True, slots=True)
class Code(Inline):
    """`` `x` ``, `{code py}[…]`, `` `#!py …` ``. Spec §Inline text."""

    type: ClassVar[Literal["Code"]] = "Code"
    text: str
    lang: str | None = None


@dataclass(frozen=True, slots=True)
class ColumnConfig(Record):
    """The optional layout trio every column-like entry carries. Mirrors Python `_ColumnAttrs` (and `ColumnConfig`, the entries of a `yaml table-config` fence, which adds nothing to it)."""

    align: Align | None = None
    width: str | None = None
    width_group: str | None = None


@dataclass(frozen=True, slots=True)
class ColumnGroup(Column):
    """A header group over an ordered list of sub-columns (recursive). Mirrors Python `ColumnGroup` (`name` required, `columns` non-empty)."""

    type: ClassVar[Literal["Group"]] = "Group"
    columns: tuple[Column, ...]
    name: str
    align: Align | None = None
    title: tuple[Inline, ...] = ()
    width: str | None = None
    width_group: str | None = None


@dataclass(frozen=True, slots=True)
class Comment(Inline):
    """`<!-- … -->`, inline or block. Spec §Comment. Zero width in the flow."""

    type: ClassVar[Literal["Comment"]] = "Comment"
    text: str


@dataclass(frozen=True, slots=True)
class CommentBlock(Block):
    """`<!-- … -->`, inline or block. Spec §Comment. Zero width in the flow."""

    type: ClassVar[Literal["Comment"]] = "Comment"
    text: str


@dataclass(frozen=True, slots=True)
class CounterDecl(Record):
    """A user-declared (or overridden) counter. Spec §Counters."""

    format: str | None = None
    name: str | None = None
    ref: str | None = None
    scope: Scope | None = None
    start: int | None = None


@dataclass(frozen=True, slots=True)
class CounterItem(Inline):
    """`{counter}(fw:x)`, `#(fw:x)`. Spec §CounterItem."""

    type: ClassVar[Literal["CounterItem"]] = "CounterItem"
    key: str
    prefix: str
    key_span: Span = NO_SPAN


@dataclass(frozen=True, slots=True)
class DataRow(Row):
    """A row of data: one cell per leaf column, in column order. Mirrors Python `DataRow` (`label`, `cells`, `source`) after `build_matrix`: the label is the first leaf cell (the first top-level column is the label column), the top-level cells are expanded into leaves."""

    type: ClassVar[Literal["Data"]] = "Data"
    cells: tuple[Cell, ...] = ()
    named: bool = False


@dataclass(frozen=True, slots=True)
class DefinitionList(Block):
    """PHP-Markdown-Extra definition list. Spec §DefinitionList. Each item is a term and its definitions."""

    type: ClassVar[Literal["DefinitionList"]] = "DefinitionList"
    items: tuple[tuple[tuple[Inline, ...], tuple[tuple[Block, ...], ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentTarget(Target):
    """Another document, `[](other.md)`."""

    type: ClassVar[Literal["Document"]] = "Document"
    value: str


@dataclass(frozen=True, slots=True)
class Emph(Inline):
    """`*x*`. Spec §Inline text."""

    type: ClassVar[Literal["Emph"]] = "Emph"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Epigraph(Record):
    """Spec §BlockQuote: `epigraph: {quote, source}` placed before the first heading."""

    quote: str
    source: str | None = None


@dataclass(frozen=True, slots=True)
class Footnote(Record):
    """A `[^label]: …` definition. Spec §Note."""

    label: str
    content: tuple[Block, ...] = ()
    id: int = field(default=0, compare=False, kw_only=True)
    span: Span = field(default=NO_SPAN, compare=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class GlossaryDecl(Record):
    """The glossary declaration, `declare.glossary`. Spec §Glossary and acronyms: two spellings reach this one struct."""

    entries: dict[str, GlossaryEntry] = field(default_factory=dict)
    groups: dict[str, GlossaryGroup] = field(default_factory=dict)
    style: str | None = None


@dataclass(frozen=True, slots=True)
class GlossaryEntry(Record):
    """A glossary term. `api: An interface` sets `description`; the object form takes `name` (the short form), `description`, `long` and the `group` the entry belongs to."""

    description: str | None = None
    group: str | None = None
    long: str | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class GlossaryGroup(Record):
    """A glossary group: `core: Core terms` or `core: {title: Core terms}`."""

    title: str = ""


@dataclass(frozen=True, slots=True)
class Highlight(Inline):
    """`{mark}[x]`, `==x==`. Spec §Inline text."""

    type: ClassVar[Literal["Highlight"]] = "Highlight"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class HorizontalRule(Block):
    """`---`: a divider. Spec §HorizontalRule."""

    type: ClassVar[Literal["HorizontalRule"]] = "HorizontalRule"


@dataclass(frozen=True, slots=True)
class Include(Block):
    """`{include}(file)` alone on its line. Spec §Includes. TeXSmith splices."""

    type: ClassVar[Literal["Include"]] = "Include"
    path: str
    base: str | None = None


@dataclass(frozen=True, slots=True)
class IndexEntry(Inline):
    """`{index}[a][b]`, `#[a][b]`. Spec §IndexEntry."""

    type: ClassVar[Literal["IndexEntry"]] = "IndexEntry"
    main: bool = False
    path: tuple[tuple[Inline, ...], ...] = ()
    registry: str | None = None


@dataclass(frozen=True, slots=True)
class Keystroke(Inline):
    """`{keys}[ctrl+s]`, `++ctrl+s++`. Spec §Inline text."""

    type: ClassVar[Literal["Keystroke"]] = "Keystroke"
    keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LeafColumn(Column):
    """A terminal column. Mirrors Python `LeafColumn`: `name` is `None` when the column has no header label; a table whose columns all lack a name has no header row. A bare scalar column descriptor (`Fruit`, `2024`) is a leaf named by its text."""

    type: ClassVar[Literal["Leaf"]] = "Leaf"
    align: Align | None = None
    name: str | None = None
    title: tuple[Inline, ...] = ()
    width: str | None = None
    width_group: str | None = None


@dataclass(frozen=True, slots=True)
class LineBreak(Inline):
    """A hard line break (trailing `\\`). Spec §HorizontalRule."""

    type: ClassVar[Literal["LineBreak"]] = "LineBreak"


@dataclass(frozen=True, slots=True)
class Link(Inline):
    """`[text](target "title")`. Spec §Ref (textual references)."""

    type: ClassVar[Literal["Link"]] = "Link"
    target: Target
    content: tuple[Inline, ...] = ()
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ListItem(Record):
    """A list item. Spec §BulletList, OrderedList."""

    content: tuple[Block, ...] = ()
    task: Task | None = None


@dataclass(frozen=True, slots=True)
class Math(Inline):
    """`$…$`. Spec §Math (inline). Display math is [`MathBlock`]; `display` is kept for `\\[…\\]` inside a paragraph."""

    type: ClassVar[Literal["Math"]] = "Math"
    text: str
    display: bool = False


@dataclass(frozen=True, slots=True)
class Note(Inline):
    """A footnote: `[^label]` refers to a [`Footnote`] definition, `^[text]` is inline and carries its `content`. Exactly one of the two is set. Spec §Note."""

    type: ClassVar[Literal["Note"]] = "Note"
    content: tuple[Block, ...] = ()
    label: str | None = None


@dataclass(frozen=True, slots=True)
class OrderedList(Block):
    """`1.` list. Spec §BulletList, OrderedList."""

    type: ClassVar[Literal["OrderedList"]] = "OrderedList"
    items: tuple[ListItem, ...] = ()
    start: int = 0
    style: ListStyle = ListStyle.DECIMAL


@dataclass(frozen=True, slots=True)
class Para(Block):
    """A paragraph, with an optional `{lead}[…]` run-in. Spec §Para."""

    type: ClassVar[Literal["Para"]] = "Para"
    lead: tuple[Inline, ...] | None = None
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Plain(Block):
    """Inline content without paragraph semantics (tight list items)."""

    type: ClassVar[Literal["Plain"]] = "Plain"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Quoted(Inline):
    """`"x"`, `'x'`. Spec §Inline text."""

    type: ClassVar[Literal["Quoted"]] = "Quoted"
    content: tuple[Inline, ...] = ()
    kind: QuoteKind = QuoteKind.DOUBLE


@dataclass(frozen=True, slots=True)
class RawBlock(Block):
    """`latex raw` fence. Spec §Raw passthrough. `format=html` is an HTML block kept as typed; `format=markdown` is a foreign directive (spec §Foreign directive: `[TOC]`, a dotted `::: a.b` line with its indented continuation) kept verbatim, printed as typed and rendered by no other writer."""

    type: ClassVar[Literal["RawBlock"]] = "RawBlock"
    format: str
    text: str


@dataclass(frozen=True, slots=True)
class RawInline(Inline):
    """`{raw latex}(…)`. Spec §Raw passthrough. `format=html` is a tag or an HTML block kept as typed."""

    type: ClassVar[Literal["RawInline"]] = "RawInline"
    format: str
    text: str


@dataclass(frozen=True, slots=True)
class Ref(Inline):
    """`@key`, `@[key, locator; key2]`. Spec §Ref, §Cite. Resolution decides label versus citation versus glossary."""

    type: ClassVar[Literal["Ref"]] = "Ref"
    bracketed: bool = False
    items: tuple[RefItem, ...] = ()


@dataclass(frozen=True, slots=True)
class RefItem(Record):
    """One item of a reference or citation group. Spec §Ref, §Cite (Pandoc's item grammar)."""

    key: str
    key_span: Span = NO_SPAN
    prefix: str | None = None
    suffix: str | None = None
    suppress_author: bool = False


@dataclass(frozen=True, slots=True)
class Separator(Row):
    """A horizontal rule between rows, optionally labelled. Mirrors Python `Separator` (written `separator: true` with `label`/`double-rule` next to it, or `separator: {label, double-rule}`)."""

    type: ClassVar[Literal["Separator"]] = "Separator"
    double_rule: bool = False
    label: str | None = None


@dataclass(frozen=True, slots=True)
class SmallCaps(Inline):
    """`{sc}[x]`, `__x__`. Spec §Inline text."""

    type: ClassVar[Literal["SmallCaps"]] = "SmallCaps"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class SoftBreak(Inline):
    """A newline inside a paragraph, kept so prose is not re-wrapped (design §Node catalogue)."""

    type: ClassVar[Literal["SoftBreak"]] = "SoftBreak"


@dataclass(frozen=True, slots=True)
class Sources(Record):
    """`sources`: where references resolve. Spec §Bibliography, §Cross-document references."""

    bibliography: JsonValue = None
    crossrefs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Space(Inline):
    """Inter-word space."""

    type: ClassVar[Literal["Space"]] = "Space"


@dataclass(frozen=True, slots=True)
class Str(Inline):
    """A run of text. Spec §Inline text."""

    type: ClassVar[Literal["Str"]] = "Str"
    text: str


@dataclass(frozen=True, slots=True)
class Strikeout(Inline):
    """`{del}[x]`, `~~x~~`. Spec §Inline text."""

    type: ClassVar[Literal["Strikeout"]] = "Strikeout"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Strong(Inline):
    """`**x**`. Spec §Inline text."""

    type: ClassVar[Literal["Strong"]] = "Strong"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Subscript(Inline):
    """`{sub}[x]`, `~x~`. Spec §Inline text."""

    type: ClassVar[Literal["Subscript"]] = "Subscript"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Superscript(Inline):
    """`{sup}[x]`, `^x^`. Spec §Inline text."""

    type: ClassVar[Literal["Superscript"]] = "Superscript"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class TableSettings(Record):
    """Knobs of the `table:` section of a `yaml table` or `yaml table-config` payload. Spec §Table rung 5 (`long` and `placement`). Mirrors Python `TableSettings` (`extra="forbid"`: an unknown key is `table-unknown-key`)."""

    long: bool | None = None
    placement: str | None = None
    width: str = 'auto'


@dataclass(frozen=True, slots=True)
class Underline(Inline):
    """`{underline}[x]`. Spec §Inline text."""

    type: ClassVar[Literal["Underline"]] = "Underline"
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Url(Target):
    """An external URL."""

    type: ClassVar[Literal["Url"]] = "Url"
    value: str


@dataclass(frozen=True, slots=True)
class Var(Inline):
    """`{{ press.template }}`. Spec §Front matter (moustaches)."""

    type: ClassVar[Literal["Var"]] = "Var"
    path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Admonition(Block):
    """`::: warning {title="…"}`, `!!! warning "…"`. Spec §Admonition. `collapsed` is an attribute."""

    type: ClassVar[Literal["Admonition"]] = "Admonition"
    kind: str
    title: tuple[Inline, ...] | None = None
    content: tuple[Block, ...] = ()
    attrs: Attrs = field(default_factory=Attrs)


@dataclass(frozen=True, slots=True)
class BlockQuote(Block):
    """`>`. Spec §BlockQuote; `.epigraph` is a class."""

    type: ClassVar[Literal["BlockQuote"]] = "BlockQuote"
    attrs: Attrs = field(default_factory=Attrs)
    content: tuple[Block, ...] = ()


@dataclass(frozen=True, slots=True)
class Caption(Block):
    """`Kind: text {#id}` caption line. Spec §Caption. The anchor lives in `attrs`; `position` is what the printer normalises."""

    type: ClassVar[Literal["Caption"]] = "Caption"
    kind: CaptionKind
    attrs: Attrs = field(default_factory=Attrs)
    content: tuple[Inline, ...] = ()
    position: CaptionPosition = CaptionPosition.AFTER


@dataclass(frozen=True, slots=True)
class CodeBlock(Block):
    """A fenced or indented code block. Spec §CodeBlock, listing. `options` holds the info-string keys (`title`, `linenums`, `hl_lines`, `include`)."""

    type: ClassVar[Literal["CodeBlock"]] = "CodeBlock"
    text: str
    lang: str | None = None
    options: Attrs = field(default_factory=Attrs)


@dataclass(frozen=True, slots=True)
class Declare(Record):
    """`declare`: what things *are*. Spec §Front matter, §Counters, §Admonition, §Glossary and acronyms."""

    acronyms: JsonValue = None
    admonitions: dict[str, AdmonitionDecl] = field(default_factory=dict)
    counters: dict[str, CounterDecl] = field(default_factory=dict)
    glossary: GlossaryDecl = field(default_factory=GlossaryDecl)


@dataclass(frozen=True, slots=True)
class Div(Block):
    """Any other `::: name` container. Spec §Div: the names of the closed registry (`registry::CONTAINERS`: `tabs`, `tab`, `multicolumn`, `div`) and, with a `container-unknown` diagnostic, any other name, kept so the printer round-trips it."""

    type: ClassVar[Literal["Div"]] = "Div"
    name: str
    attrs: Attrs = field(default_factory=Attrs)
    content: tuple[Block, ...] = ()


@dataclass(frozen=True, slots=True)
class Figure(Block):
    """`::: figure`. Spec §Image, Figure: the images inside are subfigures."""

    type: ClassVar[Literal["Figure"]] = "Figure"
    attrs: Attrs = field(default_factory=Attrs)
    content: tuple[Block, ...] = ()


@dataclass(frozen=True, slots=True)
class Header(Block):
    """`#` to `######`. Spec §Header. The id lives in `attrs`."""

    type: ClassVar[Literal["Header"]] = "Header"
    level: int
    attrs: Attrs = field(default_factory=Attrs)
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class Image(Inline):
    """`![alt](src){attrs}`. Spec §Image, Figure. `width`, `align`, `media` are attributes."""

    type: ClassVar[Literal["Image"]] = "Image"
    src: str
    alt: tuple[Inline, ...] = ()
    attrs: Attrs = field(default_factory=Attrs)


@dataclass(frozen=True, slots=True)
class MathBlock(Block):
    """`$$ … $$ {#eq:x}`. Spec §Math (display), equation."""

    type: ClassVar[Literal["MathBlock"]] = "MathBlock"
    text: str
    attrs: Attrs = field(default_factory=Attrs)


@dataclass(frozen=True, slots=True)
class ProgressBar(Inline):
    """`[=45% "Review"]{.thin}`. Spec §ProgressBar: an inline bar with a `value` from 0 to 100 (clamped) and an optional `label` (the percentage when absent); `.thin` and the other classes are attributes."""

    type: ClassVar[Literal["ProgressBar"]] = "ProgressBar"
    value: float
    attrs: Attrs = field(default_factory=Attrs)
    label: str | None = None


@dataclass(frozen=True, slots=True)
class SpanNode(Inline):
    """`[x]{attrs}`: the anonymous span, a host for `#id`, `lang`, `media`. Spec §Roles. Named `SpanNode` in Rust because [`Span`] is the source range; its JSON `type` is `"Span"`."""

    type: ClassVar[Literal["Span"]] = "Span"
    attrs: Attrs = field(default_factory=Attrs)
    content: tuple[Inline, ...] = ()


@dataclass(frozen=True, slots=True)
class TableConfig(Block):
    """A `yaml table-config` fence, attached to the preceding [`Table`] by a pass; kept as a node so round-trip is exact. Spec §Table rung 3."""

    type: ClassVar[Literal["TableConfig"]] = "TableConfig"
    columns: tuple[ColumnConfig, ...] = ()
    settings: TableSettings = field(default_factory=TableSettings)
    source: str | None = None


@dataclass(frozen=True, slots=True)
class TableModel(Record):
    """Spec §Table: the model every rung of the ladder lowers to. Mirrors Python `Table` (`settings`, `columns`, `rows`, `footer`). Pipe tables produce one with no spans and no groups."""

    rows: tuple[Row, ...] = ()
    footer: tuple[Row, ...] = ()
    columns: tuple[Column, ...] = ()
    settings: TableSettings = field(default_factory=TableSettings)


@dataclass(frozen=True, slots=True)
class Press(Record):
    """The `press` namespace, restricted to the keys TMark reads."""

    base_level: str | None = None
    declare: Declare = field(default_factory=Declare)
    features: dict[str, bool] = field(default_factory=dict)
    sources: Sources = field(default_factory=Sources)


@dataclass(frozen=True, slots=True)
class Table(Block):
    """A table of any rung of the ladder. Spec §Table."""

    type: ClassVar[Literal["Table"]] = "Table"
    attrs: Attrs = field(default_factory=Attrs)
    model: TableModel = field(default_factory=TableModel)
    source: str | None = None


@dataclass(frozen=True, slots=True)
class Keys(Record):
    """The typed subset of the front matter (spec §Front matter). Serialises to the canonical layout: metadata at the root, the rest under `press`."""

    authors: tuple[Author, ...] = ()
    date: str | None = None
    epigraph: Epigraph | None = None
    id: str | None = None
    lang: str | None = None
    press: Press = field(default_factory=Press)
    subtitle: str | None = None
    title: str | None | Missing = MISSING


@dataclass(frozen=True, slots=True)
class FrontMatter(Record):
    """The front matter of a document. `raw` is the YAML text between the fences, copied byte for byte by the printer (ADR 0004)."""

    deprecated: tuple[str, ...] = ()
    extra: dict[str, JsonValue] = field(default_factory=dict)
    keys: Keys = field(default_factory=Keys)
    raw: str = ""
    id: int = field(default=0, compare=False, kw_only=True)
    span: Span = field(default=NO_SPAN, compare=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class Document(Record):
    """A parsed file. Design §Shape."""

    abbreviations: tuple[AbbrDef, ...] = ()
    blocks: tuple[Block, ...] = ()
    file: int = 0
    footnotes: tuple[Footnote, ...] = ()
    front_matter: FrontMatter = field(default_factory=FrontMatter)


AnyBlock: TypeAlias = Para | Plain | Header | CodeBlock | BlockQuote | BulletList | OrderedList | DefinitionList | HorizontalRule | Table | TableConfig | Caption | Figure | Admonition | Div | MathBlock | RawBlock | Include | CommentBlock
AnyColumn: TypeAlias = LeafColumn | ColumnGroup
AnyInline: TypeAlias = Str | Space | SoftBreak | LineBreak | Emph | Strong | Strikeout | Underline | Highlight | Subscript | Superscript | SmallCaps | Quoted | Code | Math | Link | Ref | Note | Image | IndexEntry | CounterItem | Keystroke | Aside | SpanNode | Var | Abbr | Comment | RawInline | ProgressBar
AnyRow: TypeAlias = DataRow | Separator
AnyTarget: TypeAlias = Url | Anchor | DocumentTarget


class FieldSpec(NamedTuple):
    """One JSON property of a record, as ``texsmith.ir.codec`` reads it."""

    name: str
    shape: tuple[Any, ...]
    policy: str  # "required" | "always" (schema default) | "skip" (at default)
    default: Any  # the default value, or its zero-argument factory
    factory: bool = False


TAG: Final = "type"

#: Tag to variant class, per union base class.
UNIONS: Final[dict[type, dict[str, type]]] = {
    Block: {
        "Para": Para,
        "Plain": Plain,
        "Header": Header,
        "CodeBlock": CodeBlock,
        "BlockQuote": BlockQuote,
        "BulletList": BulletList,
        "OrderedList": OrderedList,
        "DefinitionList": DefinitionList,
        "HorizontalRule": HorizontalRule,
        "Table": Table,
        "TableConfig": TableConfig,
        "Caption": Caption,
        "Figure": Figure,
        "Admonition": Admonition,
        "Div": Div,
        "MathBlock": MathBlock,
        "RawBlock": RawBlock,
        "Include": Include,
        "Comment": CommentBlock,
    },
    Column: {
        "Leaf": LeafColumn,
        "Group": ColumnGroup,
    },
    Inline: {
        "Str": Str,
        "Space": Space,
        "SoftBreak": SoftBreak,
        "LineBreak": LineBreak,
        "Emph": Emph,
        "Strong": Strong,
        "Strikeout": Strikeout,
        "Underline": Underline,
        "Highlight": Highlight,
        "Subscript": Subscript,
        "Superscript": Superscript,
        "SmallCaps": SmallCaps,
        "Quoted": Quoted,
        "Code": Code,
        "Math": Math,
        "Link": Link,
        "Ref": Ref,
        "Note": Note,
        "Image": Image,
        "IndexEntry": IndexEntry,
        "CounterItem": CounterItem,
        "Keystroke": Keystroke,
        "Aside": Aside,
        "Span": SpanNode,
        "Var": Var,
        "Abbr": Abbr,
        "Comment": Comment,
        "RawInline": RawInline,
        "ProgressBar": ProgressBar,
    },
    Row: {
        "Data": DataRow,
        "Separator": Separator,
    },
    Target: {
        "Url": Url,
        "Anchor": Anchor,
        "Document": DocumentTarget,
    },
}

#: JSON properties of every record and variant, in dataclass order.
FIELDS: Final[dict[type, tuple[FieldSpec, ...]]] = {
    Abbr: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    AbbrDef: (
        FieldSpec("expansion", ("str",), "required", None),
        FieldSpec("key", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Admonition: (
        FieldSpec("kind", ("str",), "required", None),
        FieldSpec("title", ("opt", ("list", ("union", Inline))), "skip", None),
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    AdmonitionDecl: (
        FieldSpec("counter", ("opt", ("str",)), "skip", None),
        FieldSpec("group", ("opt", ("str",)), "skip", None),
        FieldSpec("name", ("opt", ("str",)), "skip", None),
        FieldSpec("reference", ("opt", ("str",)), "skip", None),
    ),
    Anchor: (
        FieldSpec("value", ("str",), "required", None),
    ),
    Aside: (
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("side", ("opt", ("enum", Side)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Attrs: (
        FieldSpec("classes", ("list", ("str",)), "skip", ()),
        FieldSpec("id", ("opt", ("str",)), "skip", None),
        FieldSpec("id_span", ("opt", ("span",)), "skip", None),
        FieldSpec("kv", ("list", ("tuple", (("str",), ("str",),))), "skip", ()),
    ),
    Author: (
        FieldSpec("name", ("str",), "required", None),
        FieldSpec("affiliation", ("opt", ("str",)), "skip", None),
        FieldSpec("email", ("opt", ("str",)), "skip", None),
    ),
    BlockQuote: (
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    BulletList: (
        FieldSpec("items", ("list", ("record", ListItem)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Caption: (
        FieldSpec("kind", ("enum", CaptionKind), "required", None),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("position", ("enum", CaptionPosition), "always", CaptionPosition.AFTER),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Cell: (
        FieldSpec("absorbed", ("bool",), "skip", False),
        FieldSpec("align", ("opt", ("enum", Align)), "skip", None),
        FieldSpec("cols", ("int",), "skip", 1),
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("rows", ("int",), "skip", 1),
    ),
    Code: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("lang", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    CodeBlock: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("lang", ("opt", ("str",)), "skip", None),
        FieldSpec("options", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    ColumnConfig: (
        FieldSpec("align", ("opt", ("enum", Align)), "skip", None),
        FieldSpec("width", ("opt", ("str",)), "skip", None),
        FieldSpec("width_group", ("opt", ("str",)), "skip", None),
    ),
    ColumnGroup: (
        FieldSpec("columns", ("list", ("union", Column)), "required", None),
        FieldSpec("name", ("str",), "required", None),
        FieldSpec("align", ("opt", ("enum", Align)), "skip", None),
        FieldSpec("title", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("width", ("opt", ("str",)), "skip", None),
        FieldSpec("width_group", ("opt", ("str",)), "skip", None),
    ),
    Comment: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    CommentBlock: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    CounterDecl: (
        FieldSpec("format", ("opt", ("str",)), "skip", None),
        FieldSpec("name", ("opt", ("str",)), "skip", None),
        FieldSpec("ref", ("opt", ("str",)), "skip", None),
        FieldSpec("scope", ("opt", ("enum", Scope)), "skip", None),
        FieldSpec("start", ("opt", ("int",)), "skip", None),
    ),
    CounterItem: (
        FieldSpec("key", ("str",), "required", None),
        FieldSpec("prefix", ("str",), "required", None),
        FieldSpec("key_span", ("span",), "always", NO_SPAN),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    DataRow: (
        FieldSpec("cells", ("list", ("record", Cell)), "skip", ()),
        FieldSpec("named", ("bool",), "skip", False),
    ),
    Declare: (
        FieldSpec("acronyms", ("any",), "skip", None),
        FieldSpec("admonitions", ("map", ("record", AdmonitionDecl)), "skip", dict, True),
        FieldSpec("counters", ("map", ("record", CounterDecl)), "skip", dict, True),
        FieldSpec("glossary", ("record", GlossaryDecl), "skip", GlossaryDecl, True),
    ),
    DefinitionList: (
        FieldSpec("items", ("list", ("tuple", (("list", ("union", Inline)), ("list", ("list", ("union", Block))),))), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Div: (
        FieldSpec("name", ("str",), "required", None),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Document: (
        FieldSpec("abbreviations", ("list", ("record", AbbrDef)), "skip", ()),
        FieldSpec("blocks", ("list", ("union", Block)), "skip", ()),
        FieldSpec("file", ("int",), "always", 0),
        FieldSpec("footnotes", ("list", ("record", Footnote)), "skip", ()),
        FieldSpec("front_matter", ("record", FrontMatter), "always", FrontMatter, True),
    ),
    DocumentTarget: (
        FieldSpec("value", ("str",), "required", None),
    ),
    Emph: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Epigraph: (
        FieldSpec("quote", ("str",), "required", None),
        FieldSpec("source", ("opt", ("str",)), "skip", None),
    ),
    Figure: (
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Footnote: (
        FieldSpec("label", ("str",), "required", None),
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    FrontMatter: (
        FieldSpec("deprecated", ("list", ("str",)), "skip", ()),
        FieldSpec("extra", ("any",), "skip", dict, True),
        FieldSpec("keys", ("record", Keys), "always", Keys, True),
        FieldSpec("raw", ("str",), "skip", ""),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    GlossaryDecl: (
        FieldSpec("entries", ("map", ("record", GlossaryEntry)), "skip", dict, True),
        FieldSpec("groups", ("map", ("record", GlossaryGroup)), "skip", dict, True),
        FieldSpec("style", ("opt", ("str",)), "skip", None),
    ),
    GlossaryEntry: (
        FieldSpec("description", ("opt", ("str",)), "skip", None),
        FieldSpec("group", ("opt", ("str",)), "skip", None),
        FieldSpec("long", ("opt", ("str",)), "skip", None),
        FieldSpec("name", ("opt", ("str",)), "skip", None),
    ),
    GlossaryGroup: (
        FieldSpec("title", ("str",), "skip", ""),
    ),
    Header: (
        FieldSpec("level", ("int",), "required", None),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Highlight: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    HorizontalRule: (
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Image: (
        FieldSpec("src", ("str",), "required", None),
        FieldSpec("alt", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Include: (
        FieldSpec("path", ("str",), "required", None),
        FieldSpec("base", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    IndexEntry: (
        FieldSpec("main", ("bool",), "skip", False),
        FieldSpec("path", ("list", ("list", ("union", Inline))), "skip", ()),
        FieldSpec("registry", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Keys: (
        FieldSpec("authors", ("list", ("record", Author)), "skip", ()),
        FieldSpec("date", ("opt", ("str",)), "skip", None),
        FieldSpec("epigraph", ("opt", ("record", Epigraph)), "skip", None),
        FieldSpec("id", ("opt", ("str",)), "skip", None),
        FieldSpec("lang", ("opt", ("str",)), "skip", None),
        FieldSpec("press", ("record", Press), "skip", Press, True),
        FieldSpec("subtitle", ("opt", ("str",)), "skip", None),
        FieldSpec("title", ("opt", ("str",)), "skip", MISSING),
    ),
    Keystroke: (
        FieldSpec("keys", ("list", ("str",)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    LeafColumn: (
        FieldSpec("align", ("opt", ("enum", Align)), "skip", None),
        FieldSpec("name", ("opt", ("str",)), "skip", None),
        FieldSpec("title", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("width", ("opt", ("str",)), "skip", None),
        FieldSpec("width_group", ("opt", ("str",)), "skip", None),
    ),
    LineBreak: (
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Link: (
        FieldSpec("target", ("union", Target), "required", None),
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("title", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    ListItem: (
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("task", ("opt", ("enum", Task)), "skip", None),
    ),
    Math: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("display", ("bool",), "skip", False),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    MathBlock: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Note: (
        FieldSpec("content", ("list", ("union", Block)), "skip", ()),
        FieldSpec("label", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    OrderedList: (
        FieldSpec("items", ("list", ("record", ListItem)), "skip", ()),
        FieldSpec("start", ("int",), "always", 0),
        FieldSpec("style", ("enum", ListStyle), "always", ListStyle.DECIMAL),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Para: (
        FieldSpec("lead", ("opt", ("list", ("union", Inline))), "skip", None),
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Plain: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Press: (
        FieldSpec("base_level", ("opt", ("str",)), "skip", None),
        FieldSpec("declare", ("record", Declare), "skip", Declare, True),
        FieldSpec("features", ("map", ("bool",)), "skip", dict, True),
        FieldSpec("sources", ("record", Sources), "skip", Sources, True),
    ),
    ProgressBar: (
        FieldSpec("value", ("float",), "required", None),
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("label", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Quoted: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("kind", ("enum", QuoteKind), "always", QuoteKind.DOUBLE),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    RawBlock: (
        FieldSpec("format", ("str",), "required", None),
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    RawInline: (
        FieldSpec("format", ("str",), "required", None),
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Ref: (
        FieldSpec("bracketed", ("bool",), "skip", False),
        FieldSpec("items", ("list", ("record", RefItem)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    RefItem: (
        FieldSpec("key", ("str",), "required", None),
        FieldSpec("key_span", ("span",), "always", NO_SPAN),
        FieldSpec("prefix", ("opt", ("str",)), "skip", None),
        FieldSpec("suffix", ("opt", ("str",)), "skip", None),
        FieldSpec("suppress_author", ("bool",), "skip", False),
    ),
    Separator: (
        FieldSpec("double_rule", ("bool",), "skip", False),
        FieldSpec("label", ("opt", ("str",)), "skip", None),
    ),
    SmallCaps: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    SoftBreak: (
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Sources: (
        FieldSpec("bibliography", ("any",), "skip", None),
        FieldSpec("crossrefs", ("map", ("str",)), "skip", dict, True),
    ),
    Space: (
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    SpanNode: (
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Str: (
        FieldSpec("text", ("str",), "required", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Strikeout: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Strong: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Subscript: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Superscript: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Table: (
        FieldSpec("attrs", ("record", Attrs), "skip", Attrs, True),
        FieldSpec("model", ("record", TableModel), "always", TableModel, True),
        FieldSpec("source", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    TableConfig: (
        FieldSpec("columns", ("list", ("record", ColumnConfig)), "skip", ()),
        FieldSpec("settings", ("record", TableSettings), "always", TableSettings, True),
        FieldSpec("source", ("opt", ("str",)), "skip", None),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    TableModel: (
        FieldSpec("rows", ("list", ("union", Row)), "skip", ()),
        FieldSpec("footer", ("list", ("union", Row)), "skip", ()),
        FieldSpec("columns", ("list", ("union", Column)), "skip", ()),
        FieldSpec("settings", ("record", TableSettings), "always", TableSettings, True),
    ),
    TableSettings: (
        FieldSpec("long", ("opt", ("bool",)), "skip", None),
        FieldSpec("placement", ("opt", ("str",)), "skip", None),
        FieldSpec("width", ("str",), "always", 'auto'),
    ),
    Underline: (
        FieldSpec("content", ("list", ("union", Inline)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
    Url: (
        FieldSpec("value", ("str",), "required", None),
    ),
    Var: (
        FieldSpec("path", ("list", ("str",)), "skip", ()),
        FieldSpec("id", ("int",), "always", 0),
        FieldSpec("span", ("span",), "always", NO_SPAN),
    ),
}

ROOT: Final = Document

__all__ = [
    "Abbr",
    "AbbrDef",
    "Admonition",
    "AdmonitionDecl",
    "Align",
    "Anchor",
    "AnyBlock",
    "AnyColumn",
    "AnyInline",
    "AnyRow",
    "AnyTarget",
    "Aside",
    "Attrs",
    "Author",
    "Block",
    "BlockQuote",
    "BulletList",
    "Caption",
    "CaptionKind",
    "CaptionPosition",
    "Cell",
    "Code",
    "CodeBlock",
    "Column",
    "ColumnConfig",
    "ColumnGroup",
    "Comment",
    "CommentBlock",
    "CounterDecl",
    "CounterItem",
    "DataRow",
    "Declare",
    "DefinitionList",
    "Div",
    "Document",
    "DocumentTarget",
    "Emph",
    "Epigraph",
    "FIELDS",
    "FieldSpec",
    "Figure",
    "Footnote",
    "FrontMatter",
    "GlossaryDecl",
    "GlossaryEntry",
    "GlossaryGroup",
    "Header",
    "Highlight",
    "HorizontalRule",
    "Image",
    "Include",
    "IndexEntry",
    "Inline",
    "JsonValue",
    "Keys",
    "Keystroke",
    "LeafColumn",
    "LineBreak",
    "Link",
    "ListItem",
    "ListStyle",
    "MISSING",
    "Math",
    "MathBlock",
    "Missing",
    "NO_SPAN",
    "Node",
    "Note",
    "OrderedList",
    "Para",
    "Plain",
    "Press",
    "ProgressBar",
    "QuoteKind",
    "Quoted",
    "ROOT",
    "RawBlock",
    "RawInline",
    "Record",
    "Ref",
    "RefItem",
    "Row",
    "SCHEMA_HASH",
    "Scope",
    "Separator",
    "Side",
    "SmallCaps",
    "SoftBreak",
    "Sources",
    "Space",
    "Span",
    "SpanNode",
    "Str",
    "Strikeout",
    "Strong",
    "SubSpan",
    "Subscript",
    "Superscript",
    "TAG",
    "TMARK_VERSION",
    "Table",
    "TableConfig",
    "TableModel",
    "TableSettings",
    "Target",
    "Task",
    "UNIONS",
    "Underline",
    "Url",
    "Var",
]
