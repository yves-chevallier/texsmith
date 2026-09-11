"""TeXSmith intermediate representation (IR).

The semantic, backend-agnostic document tree consumed by every writer and
produced by every reader. See :mod:`texsmith.ir.nodes` for the sealed
``Block`` / ``Inline`` hierarchy and the transverse-state map, and
:mod:`texsmith.ir.visitor` for traversal utilities.
"""

from __future__ import annotations

# The tmark-shaped models (``model``, ``codec``, ``walk``) live beside the
# legacy ``nodes`` during the migration (specs/tmark-migration.md R3); the
# legacy tree stays the default export until phase 3.8. The ``walk`` module
# is imported first so that the legacy ``ir.walk`` *function* below keeps the
# name: a submodule only binds itself on its package when it is first loaded.
import texsmith.ir.walk as _walk_module  # isort: split


from texsmith.ir import codec, model
from texsmith.ir.nodes import (
    Admonition,
    AnyNode,
    Block,
    BlockQuote,
    BulletList,
    Cite,
    Code,
    CodeBlock,
    DefinitionItem,
    DefinitionList,
    Div,
    Document,
    Emph,
    Figure,
    Header,
    Highlight,
    HorizontalRule,
    Image,
    IndexEntry,
    Inline,
    Keystroke,
    LineBreak,
    Link,
    ListStyle,
    MarginNote,
    MarginSide,
    Math,
    Node,
    Note,
    OrderedList,
    Para,
    Plain,
    ProgressBar,
    Quoted,
    RawBlock,
    RawInline,
    SmallCaps,
    SoftBreak,
    Space,
    Span,
    Str,
    Strikeout,
    Strong,
    Subscript,
    Superscript,
    Table,
    TexLogo,
    Underline,
)
from texsmith.ir.visitor import (
    NodeVisitor,
    children,
    iter_child_fields,
    map_tree,
    walk,
)


del _walk_module

_mismatch = codec.wheel_schema_mismatch()
if _mismatch is not None:
    raise ImportError(_mismatch)
del _mismatch


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
    "NodeVisitor",
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
    "children",
    "iter_child_fields",
    "map_tree",
    "walk",
]
