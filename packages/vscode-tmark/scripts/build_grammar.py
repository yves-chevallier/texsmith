#!/usr/bin/env python3
"""Generate the TMark TextMate grammars from the recognisers of specs/tmark.md.

Two files are written next to this script, under ``syntaxes/``:

* ``tmark.tmLanguage.json`` — the grammar of the ``tmark`` language
  (scope ``text.html.markdown.tmark``). It holds every TMark rule in its
  repository and falls back to VS Code's Markdown grammar for the rest.
* ``tmark.injection.tmLanguage.json`` — an injection grammar that adds the
  same rules to every Markdown document (``L:text.html.markdown``), so that
  ``.md`` files keep the built-in Markdown language and its features.

The regexes are written as Python raw strings so that the JSON escaping is
handled by ``json.dump`` rather than by hand. Run ``python3 scripts/build_grammar.py``
(or ``npm run build:grammar``) after editing, then ``npm test``.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNTAXES = ROOT / "syntaxes"

MD_INLINE = {"include": "text.html.markdown#inline"}
MD_BLOCK = {"include": "text.html.markdown#block"}

# Fragments shared by several recognisers (§ Lexical grammar).
ID = r"[\w:.-]+"
VALUE = r'"[^"]*"|[^\s}]+'
KV = rf"[\w-]+=(?:{VALUE})"
ATTR_ITEMS = rf"(?:[ \t]*(?:#{ID}|\.[\w-]+|{KV}))+"
REF_KEY = r"[A-Za-z][\w:.-]*[A-Za-z0-9]"
REF_GUARD = r"(?<![\w@/:.-])"          # X4: never inside a word, an e-mail or a URL
DEFINE_GUARD = r"(?<![\\\w])"           # X5: `\#` escapes
LINE_START = r"(^|\G)(?<!\S)"           # start of line, or right after a block marker

ROLES = [
    "index", "aside", "raw", "include", "counter", "code", "lead",
    "sc", "del", "underline", "mark", "sub", "sup", "keys",
    # deprecated spellings, still accepted (Appendix "Deprecation schedule")
    "margin", "latex", "typst", "html",
]
DEPRECATED_ROLES = ["margin", "latex", "typst", "html"]
NODE_WORDS = "code|table-config|table|image|raw"

# Data directives: which fenced languages embed which grammar.
FENCE_LANGUAGES = [
    ("yaml", r"yaml|yml", "source.yaml"),
    ("python", r"python|py|py3", "source.python"),
    ("latex", r"latex|tex", "text.tex.latex"),
    ("html", r"html|htm", "text.html.basic"),
    ("typst", r"typst|typ", "source.typst"),
    ("mermaid", r"mermaid", "source.mermaid"),
    ("tmark", r"[\w+-]+", None),
]


def kv_patterns(prefix: str) -> list[dict]:
    """`key=value` items, quoted or bare."""
    return [
        {
            "match": rf"([\w-]+)(=)({VALUE})",
            "captures": {
                "1": {"name": f"entity.other.attribute-name.{prefix}.tmark"},
                "2": {"name": "punctuation.separator.key-value.tmark"},
                "3": {
                    "patterns": [
                        {"match": r'"[^"]*"', "name": "string.quoted.double.tmark"},
                        {"match": r"[^\s}]+", "name": "string.unquoted.tmark"},
                    ]
                },
            },
        }
    ]


def fence_rule(name: str, langs: str, include: str | None) -> dict:
    """A fenced block whose info string carries a node word or options.

    Mirrors the shape of VS Code's ``fenced_code_block_*`` rules so that the
    embedded language keeps working; the node word and the options get scopes.
    """
    content: dict = {
        "begin": r"(^|\G)(\s*)(.*)",
        "while": r"(^|\G)(?!\s*([`~]{3,})\s*$)",
        "contentName": f"meta.embedded.block.{name}",
    }
    if include:
        content["patterns"] = [{"include": include}]
    return {
        "name": "markup.fenced_code.block.markdown meta.directive.data.tmark",
        "begin": (
            r"(^|\G)(\s*)(`{3,}|~{3,})[ \t]*"
            rf"(?i:({langs}))(?=[ \t]+\S)"
            rf"(?:[ \t]+({NODE_WORDS})\b)?"
            rf"((?:[ \t]+{KV})*)[ \t]*$"
        ),
        "beginCaptures": {
            "0": {"name": "meta.directive.head.tmark"},
            "3": {"name": "punctuation.definition.markdown"},
            "4": {"name": "fenced_code.block.language.markdown"},
            "5": {"name": "keyword.control.directive.node.tmark"},
            "6": {"patterns": kv_patterns("fence")},
        },
        "end": r"(^|\G)(\2|\s{0,3})(\3)\s*$",
        "endCaptures": {"3": {"name": "punctuation.definition.markdown"}},
        "patterns": [content],
    }


def inline_content() -> list[dict]:
    """Markdown inline plus the TMark inline rules, for bracketed content."""
    return [{"include": "#escape-bracket"}, {"include": "#inline"}, MD_INLINE]


repository: dict[str, dict] = {
    # ------------------------------------------------------------------ blocks
    "block": {
        "patterns": [
            {"include": "#container-open-deprecated"},
            {"include": "#container-open"},
            {"include": "#container-close"},
            {"include": "#admonition"},
            {"include": "#pymdownx-block"},
            {"include": "#data-directive"},
            {"include": "#caption"},
            {"include": "#definition"},
            {"include": "#footnote-def"},
            {"include": "#abbr-def"},
            {"include": "#snippet"},
            {"include": "#toc"},
            {"include": "#math-display-compat"},
        ]
    },
    "container-open-deprecated": {
        "name": "meta.directive.container.begin.tmark",
        "match": rf"{LINE_START}[ \t]*(:{{3,}})[ \t]*(margin)\b(?:[ \t]+(\{{[^}}]*\}}))?[ \t]*$",
        "captures": {
            "2": {"name": "punctuation.definition.directive.begin.tmark keyword.control.directive.tmark"},
            "3": {"name": "entity.name.type.directive.container.tmark invalid.deprecated.tmark"},
            "4": {"patterns": [{"include": "#attributes"}]},
        },
    },
    "container-open": {
        "name": "meta.directive.container.begin.tmark",
        "match": rf"{LINE_START}[ \t]*(:{{3,}})[ \t]*([A-Za-z][\w-]*)(?:[ \t]+(\{{[^}}]*\}}))?[ \t]*$",
        "captures": {
            "2": {"name": "punctuation.definition.directive.begin.tmark keyword.control.directive.tmark"},
            "3": {"name": "entity.name.type.directive.container.tmark"},
            "4": {"patterns": [{"include": "#attributes"}]},
        },
    },
    "container-close": {
        "name": "meta.directive.container.end.tmark",
        "match": rf"{LINE_START}[ \t]*(:{{3,}})[ \t]*$",
        "captures": {
            "2": {"name": "punctuation.definition.directive.end.tmark keyword.control.directive.tmark"},
        },
    },
    "admonition": {
        # PyMdownX `!!! type "Title"`, `??? type`, `???+ type`; the body is the
        # indented block that follows (blank lines allowed inside).
        "name": "meta.directive.admonition.tmark",
        "begin": (
            rf"{LINE_START}[ \t]*(!{{3}}|\?{{3}}\+?)[ \t]+([\w-]+)((?:[ \t]+[\w-]+)*)"
            r'(?:[ \t]+("(?:[^"\\]|\\.)*"))?[ \t]*$'
        ),
        "beginCaptures": {
            "0": {"name": "meta.directive.head.tmark"},
            "2": {"name": "punctuation.definition.directive.tmark keyword.control.directive.tmark"},
            "3": {"name": "entity.name.type.directive.admonition.tmark"},
            "4": {"name": "entity.other.attribute-name.class.tmark"},
            "5": {"name": "string.quoted.double.title.tmark"},
        },
        "while": r"(^|\G)(?:[ ]{4}|\t|(?=[ \t]*$))",
        "patterns": [{"include": "#block"}, MD_BLOCK],
    },
    "pymdownx-block": {
        # `/// name … ///` (deprecated)
        "name": "meta.directive.pymdownx.tmark",
        "begin": rf"{LINE_START}[ \t]*(/{{3}})[ \t]*([\w-]+)(.*)$",
        "beginCaptures": {
            "0": {"name": "meta.directive.head.tmark"},
            "2": {"name": "punctuation.definition.directive.begin.tmark keyword.control.directive.tmark invalid.deprecated.tmark"},
            "3": {"name": "entity.name.type.directive.tmark invalid.deprecated.tmark"},
            "4": {"name": "string.unquoted.directive.tmark"},
        },
        "end": rf"{LINE_START}[ \t]*(/{{3}})[ \t]*$",
        "endCaptures": {
            "2": {"name": "punctuation.definition.directive.end.tmark keyword.control.directive.tmark invalid.deprecated.tmark"},
        },
        "patterns": [{"include": "#block"}, MD_BLOCK],
    },
    "data-directive": {
        "patterns": [fence_rule(name, langs, include) for name, langs, include in FENCE_LANGUAGES]
    },
    # The three rules below open a line with a marker and hand the rest of the
    # line to the inline rules. They are begin/end rather than match rules
    # because vscode-textmate only moves the `\G` anchor after a begin match,
    # and Markdown's paragraph rule needs `\G` to start mid-line.
    "caption": {
        "name": "meta.caption.tmark",
        "begin": rf"{LINE_START}[ \t]*(Table|Figure|Listing)(:)(?=[ \t]+\S)",
        "beginCaptures": {
            "2": {"name": "keyword.other.caption.tmark"},
            "3": {"name": "punctuation.separator.caption.tmark"},
        },
        "end": r"$",
        "patterns": [{"include": "#inline"}, MD_INLINE],
    },
    "definition": {
        "name": "meta.definition.tmark",
        "begin": rf"{LINE_START}[ ]{{0,3}}(:)(?=[ ]{{1,3}}\S)",
        "beginCaptures": {
            "2": {"name": "punctuation.definition.list.begin.markdown keyword.operator.definition.tmark"},
        },
        "end": r"$",
        "patterns": [{"include": "#inline"}, MD_INLINE],
    },
    "footnote-def": {
        "name": "meta.footnote.definition.tmark",
        "begin": rf"{LINE_START}[ ]{{0,3}}(\[\^)([^\]\s]+)(\])(:)",
        "beginCaptures": {
            "2": {"name": "punctuation.definition.footnote.begin.tmark"},
            "3": {"name": "variable.other.footnote.tmark"},
            "4": {"name": "punctuation.definition.footnote.end.tmark"},
            "5": {"name": "punctuation.separator.key-value.tmark"},
        },
        "end": r"$",
        "patterns": [{"include": "#inline"}, MD_INLINE],
    },
    "abbr-def": {
        "name": "meta.abbr.definition.tmark",
        "match": rf"{LINE_START}[ ]{{0,3}}(\*\[)([^\]]+)(\]:)[ \t]*(.*)$",
        "captures": {
            "2": {"name": "punctuation.definition.abbr.begin.tmark"},
            "3": {"name": "entity.name.tag.abbr.tmark"},
            "4": {"name": "punctuation.definition.abbr.end.tmark"},
            "5": {"name": "string.unquoted.abbr.tmark"},
        },
    },
    "snippet": {
        "name": "meta.include.snippet.tmark",
        "match": rf'{LINE_START}[ \t]*(-{{2}}8<-{{2}})[ \t]+("[^"]*"|\S+)[ \t]*$',
        "captures": {
            "2": {"name": "keyword.control.include.tmark invalid.deprecated.tmark"},
            "3": {"name": "string.quoted.double.tmark"},
        },
    },
    "toc": {
        "match": rf"{LINE_START}[ \t]*(\[TOC\])[ \t]*$",
        "captures": {"2": {"name": "keyword.control.toc.tmark"}},
    },
    "math-display-compat": {
        # `\[ … \]`, the LaTeX habit accepted next to `$$ … $$`
        "name": "markup.math.block.markdown",
        "contentName": "meta.embedded.math.markdown",
        "begin": rf"{LINE_START}[ \t]*(\\\[)",
        "beginCaptures": {"2": {"name": "punctuation.definition.math.begin.markdown"}},
        "end": r"(\\\])",
        "endCaptures": {"1": {"name": "punctuation.definition.math.end.markdown"}},
        "patterns": [{"include": "text.html.markdown.math#math"}],
    },
    # ----------------------------------------------------------------- inlines
    "inline": {
        "patterns": [
            {"include": "#escape"},
            {"include": "#moustache"},
            {"include": "#critic"},
            {"include": "#role"},
            {"include": "#span"},
            {"include": "#attributes"},
            {"include": "#index-entry"},
            {"include": "#counter-item"},
            {"include": "#counter-item-deprecated"},
            {"include": "#reference-bracketed"},
            {"include": "#reference-doi-url"},
            {"include": "#reference-bare"},
            {"include": "#citation-pandoc"},
            {"include": "#footnote-ref"},
            {"include": "#footnote-inline"},
            {"include": "#task-item"},
            {"include": "#keystroke"},
            {"include": "#highlight"},
            {"include": "#insert"},
            {"include": "#superscript"},
            {"include": "#subscript"},
            {"include": "#smallcaps"},
            {"include": "#code-hilite"},
            {"include": "#progress"},
            {"include": "#math-inline-compat"},
        ]
    },
    "escape": {
        "match": r"\\[@#]",
        "name": "constant.character.escape.tmark",
    },
    "escape-bracket": {
        "match": r"\\[\[\]()]",
        "name": "constant.character.escape.tmark",
    },
    "moustache": {
        "name": "meta.moustache.tmark",
        "match": r"(\{\{)[ \t]*([\w.-]+)[ \t]*(\}\})",
        "captures": {
            "1": {"name": "punctuation.definition.moustache.begin.tmark"},
            "2": {"name": "variable.other.moustache.tmark"},
            "3": {"name": "punctuation.definition.moustache.end.tmark"},
        },
    },
    "critic": {
        "patterns": [
            {
                "name": "comment.block.critic.tmark",
                "match": r"(\{>>)(.*?)(<<\})",
                "captures": {
                    "1": {"name": "punctuation.definition.comment.begin.tmark"},
                    "3": {"name": "punctuation.definition.comment.end.tmark"},
                },
            },
            {
                "name": "markup.inserted.critic.tmark",
                "match": r"(\{\+\+)(.*?)(\+\+\})",
                "captures": {
                    "1": {"name": "punctuation.definition.inserted.begin.tmark"},
                    "3": {"name": "punctuation.definition.inserted.end.tmark"},
                },
            },
            {
                "name": "markup.deleted.critic.tmark",
                "match": r"(\{--)(.*?)(--\})",
                "captures": {
                    "1": {"name": "punctuation.definition.deleted.begin.tmark"},
                    "3": {"name": "punctuation.definition.deleted.end.tmark"},
                },
            },
            {
                "name": "markup.changed.critic.tmark",
                "match": r"(\{~~)(.*?)(~>)(.*?)(~~\})",
                "captures": {
                    "1": {"name": "punctuation.definition.changed.begin.tmark"},
                    "2": {"name": "markup.deleted.critic.tmark"},
                    "3": {"name": "punctuation.separator.changed.tmark"},
                    "4": {"name": "markup.inserted.critic.tmark"},
                    "5": {"name": "punctuation.definition.changed.end.tmark"},
                },
            },
            {
                "name": "markup.highlight.critic.tmark",
                "match": r"(\{==)(.*?)(==\})",
                "captures": {
                    "1": {"name": "punctuation.definition.highlight.begin.tmark"},
                    "3": {"name": "punctuation.definition.highlight.end.tmark"},
                },
            },
        ]
    },
    "role": {
        # `{name positional key=value}` immediately followed by `[content]`
        # (one or more groups) or `(argument)`.
        "name": "meta.role.tmark",
        "begin": (
            r"(\{)(" + "|".join(ROLES) + r")(:[\w-]+)?"
            r"(?:[ \t]+([^\s=}]+))?"
            rf"((?:[ \t]+{KV})*)[ \t]*(\}})(?=[\[(])"
        ),
        "beginCaptures": {
            "0": {"name": "meta.role.head.tmark"},
            "1": {"name": "punctuation.definition.role.begin.tmark"},
            "2": {
                "name": "entity.name.function.role.tmark",
                "patterns": [
                    {
                        "match": r"\b(" + "|".join(DEPRECATED_ROLES) + r")\b",
                        "name": "invalid.deprecated.role.tmark",
                    }
                ],
            },
            "3": {"name": "variable.parameter.registry.role.tmark invalid.deprecated.tmark"},
            "4": {"name": "variable.parameter.positional.role.tmark"},
            "5": {"patterns": kv_patterns("role")},
            "6": {"name": "punctuation.definition.role.end.tmark"},
        },
        "end": r"(?![\[(])",
        "patterns": [{"include": "#role-content"}, {"include": "#role-argument"}],
    },
    "role-content": {
        "name": "meta.role.content.tmark",
        "begin": r"\[",
        "beginCaptures": {"0": {"name": "punctuation.definition.role.content.begin.tmark"}},
        "end": r"\]|$",
        "endCaptures": {"0": {"name": "punctuation.definition.role.content.end.tmark"}},
        "patterns": inline_content(),
    },
    "role-argument": {
        "name": "string.other.argument.role.tmark",
        "begin": r"\(",
        "beginCaptures": {"0": {"name": "punctuation.definition.role.argument.begin.tmark"}},
        "end": r"\)|$",
        "endCaptures": {"0": {"name": "punctuation.definition.role.argument.end.tmark"}},
        "patterns": [{"include": "#role-argument-nested"}],
    },
    "role-argument-nested": {
        "begin": r"\(",
        "end": r"\)|$",
        "patterns": [{"include": "#role-argument-nested"}],
    },
    "span": {
        # Pandoc-style anonymous span `[text]{attrs}`
        "name": "meta.span.tmark",
        "match": rf"(\[)((?:[^\[\]\\]|\\.)+)(\])(?=\{{[ \t]*(?:#|\.|[\w-]+=))",
        "captures": {
            "1": {"name": "punctuation.definition.span.begin.tmark"},
            "2": {"patterns": inline_content()},
            "3": {"name": "punctuation.definition.span.end.tmark"},
        },
    },
    "attributes": {
        "name": "meta.attributes.tmark",
        "match": rf"(\{{)({ATTR_ITEMS})[ \t]*(\}})",
        "captures": {
            "1": {"name": "punctuation.definition.attributes.begin.tmark"},
            "2": {"patterns": [{"include": "#attribute-items"}]},
            "3": {"name": "punctuation.definition.attributes.end.tmark"},
        },
    },
    "attribute-items": {
        "patterns": [
            {
                "match": rf"(#)({ID})",
                "captures": {
                    "1": {"name": "keyword.other.sigil.define.tmark"},
                    "2": {"name": "entity.other.attribute-name.id.tmark"},
                },
            },
            {
                "match": r"(\.)([\w-]+)",
                "captures": {
                    "1": {"name": "punctuation.definition.attribute.class.tmark"},
                    "2": {"name": "entity.other.attribute-name.class.tmark"},
                },
            },
            *kv_patterns("attribute"),
        ]
    },
    "index-entry": {
        # `#[term]`, `#[term][sub]`, `#[term][sub][subsub]`
        "name": "meta.index-entry.tmark",
        "match": rf"{DEFINE_GUARD}(#)(?=\[\S)((?:\[(?:[^\[\]\\]|\\.)+\]){{1,3}})",
        "captures": {
            "1": {"name": "keyword.other.sigil.define.tmark"},
            "2": {
                "patterns": [
                    {
                        "match": r"(\[)((?:[^\[\]\\]|\\.)+)(\])",
                        "captures": {
                            "1": {"name": "punctuation.definition.index.begin.tmark"},
                            "2": {"name": "entity.other.attribute-name.index.tmark", "patterns": inline_content()},
                            "3": {"name": "punctuation.definition.index.end.tmark"},
                        },
                    }
                ]
            },
        },
    },
    "counter-item": {
        # `#(prefix:key)`: define and print a numbered item
        "name": "meta.counter-item.tmark",
        "match": rf"{DEFINE_GUARD}(#)(\()([A-Za-z][\w-]*)(:)([\w.-]+)(\))",
        "captures": {
            "1": {"name": "keyword.other.sigil.define.tmark"},
            "2": {"name": "punctuation.definition.counter.begin.tmark"},
            "3": {"name": "support.type.counter-prefix.tmark"},
            "4": {"name": "punctuation.separator.counter.tmark"},
            "5": {"name": "entity.other.attribute-name.counter.tmark"},
            "6": {"name": "punctuation.definition.counter.end.tmark"},
        },
    },
    "counter-item-deprecated": {
        # `#{prefix:key}`, the shipping spelling, deprecated
        "name": "meta.counter-item.tmark invalid.deprecated.tmark",
        "match": rf"{DEFINE_GUARD}(#)(\{{)([A-Za-z][\w-]*)(:)([\w.-]+)(\}})",
        "captures": {
            "1": {"name": "keyword.other.sigil.define.tmark"},
            "2": {"name": "punctuation.definition.counter.begin.tmark"},
            "3": {"name": "support.type.counter-prefix.tmark"},
            "4": {"name": "punctuation.separator.counter.tmark"},
            "5": {"name": "entity.other.attribute-name.counter.tmark"},
            "6": {"name": "punctuation.definition.counter.end.tmark"},
        },
    },
    "reference-items": {
        "patterns": [
            {"match": r";", "name": "punctuation.separator.reference.tmark"},
            {"match": r"(?<![\w:.-])-(?=[A-Za-z])", "name": "keyword.operator.suppress-author.tmark"},
        ]
    },
    "reference-bracketed": {
        # `@[key, locator; key2]`
        "name": "meta.reference.bracketed.tmark",
        "match": rf"{REF_GUARD}(@)(\[)([^\[\]]*)(\])",
        "captures": {
            "1": {"name": "keyword.other.sigil.refer.tmark"},
            "2": {"name": "punctuation.definition.reference.begin.tmark"},
            "3": {"name": "support.type.reference.tmark", "patterns": [{"include": "#reference-items"}]},
            "4": {"name": "punctuation.definition.reference.end.tmark"},
        },
    },
    "reference-doi-url": {
        # `@https://doi.org/…`, sugar for `@doi:…`
        "name": "meta.reference.bare.tmark",
        "match": rf"{REF_GUARD}(@)(https?://[^\s\[\]()]*[^\s\[\]().,;:])",
        "captures": {
            "1": {"name": "keyword.other.sigil.refer.tmark"},
            "2": {"name": "support.type.reference.tmark"},
        },
    },
    "reference-bare": {
        # `@sec:intro`, `@ein05`, `@Fig:x`; a `doi:` key may hold a `/`
        "name": "meta.reference.bare.tmark",
        "match": rf"{REF_GUARD}(@)((?i:doi):[^\s\[\]()]*[^\s\[\]().,;:]|{REF_KEY})",
        "captures": {
            "1": {"name": "keyword.other.sigil.refer.tmark"},
            "2": {"name": "support.type.reference.tmark"},
        },
    },
    "citation-pandoc": {
        # Pandoc's `[@key, locator; -@key2]`, accepted for import
        "name": "meta.reference.pandoc.tmark",
        "match": rf"(\[)(-?@{REF_KEY}[^\]]*)(\])",
        "captures": {
            "1": {"name": "punctuation.definition.reference.begin.tmark"},
            "2": {
                "name": "support.type.reference.tmark",
                "patterns": [
                    {"match": r"@", "name": "keyword.other.sigil.refer.tmark"},
                    {"include": "#reference-items"},
                ],
            },
            "3": {"name": "punctuation.definition.reference.end.tmark"},
        },
    },
    "footnote-ref": {
        "name": "meta.footnote.reference.tmark",
        "match": r"(\[\^)([^\]\s]+)(\])(?!:)",
        "captures": {
            "1": {"name": "punctuation.definition.footnote.begin.tmark"},
            "2": {"name": "variable.other.footnote.tmark"},
            "3": {"name": "punctuation.definition.footnote.end.tmark"},
        },
    },
    "footnote-inline": {
        # `^[text]` (proposed inline footnote; today the deprecated citation sugar)
        "name": "meta.footnote.inline.tmark",
        "match": r"(?<![\w\\])(\^\[)([^\]]*)(\])",
        "captures": {
            "1": {"name": "punctuation.definition.footnote.begin.tmark"},
            "2": {"patterns": inline_content()},
            "3": {"name": "punctuation.definition.footnote.end.tmark"},
        },
    },
    "task-item": {
        # `- [ ]`, `- [x]`, `- [.]` right after a list marker; the rest of the
        # line is inline content (see the note on `\G` above).
        "name": "meta.task.tmark",
        "begin": r"\G(\[[ xX.]\])(?=[ \t])",
        "beginCaptures": {"1": {"name": "constant.language.task.tmark"}},
        "end": r"$",
        "patterns": [{"include": "#inline"}, MD_INLINE],
    },
    "keystroke": {
        "name": "markup.keystroke.tmark",
        "match": r"(\+\+)([\w-]+(?:\+[\w-]+)*)(\+\+)",
        "captures": {
            "1": {"name": "punctuation.definition.keystroke.begin.tmark"},
            "2": {
                "name": "markup.inline.raw.keystroke.tmark",
                "patterns": [{"match": r"\+", "name": "punctuation.separator.keystroke.tmark"}],
            },
            "3": {"name": "punctuation.definition.keystroke.end.tmark"},
        },
    },
    "highlight": {
        "name": "markup.highlight.tmark",
        "match": r"(?<![=\\])(==)(?=\S)((?:[^=]|=(?!=))+?)(?<=\S)(==)(?!=)",
        "captures": {
            "1": {"name": "punctuation.definition.highlight.begin.tmark"},
            "2": {"patterns": inline_content()},
            "3": {"name": "punctuation.definition.highlight.end.tmark"},
        },
    },
    "insert": {
        "name": "markup.underline.insert.tmark",
        "match": r"(?<![\^\\])(\^\^)(?=\S)((?:[^\^]|\^(?!\^))+?)(?<=\S)(\^\^)(?!\^)",
        "captures": {
            "1": {"name": "punctuation.definition.insert.begin.tmark"},
            "2": {"patterns": inline_content()},
            "3": {"name": "punctuation.definition.insert.end.tmark"},
        },
    },
    "superscript": {
        "name": "markup.superscript.tmark",
        "match": r"(?<![\^\\])(\^)([^\^\s\[]+?)(\^)(?!\^)",
        "captures": {
            "1": {"name": "punctuation.definition.superscript.begin.tmark"},
            "3": {"name": "punctuation.definition.superscript.end.tmark"},
        },
    },
    "subscript": {
        "name": "markup.subscript.tmark",
        "match": r"(?<![~\\])(~)([^~\s]+?)(~)(?!~)",
        "captures": {
            "1": {"name": "punctuation.definition.subscript.begin.tmark"},
            "3": {"name": "punctuation.definition.subscript.end.tmark"},
        },
    },
    "smallcaps": {
        # X1: `__x__` is small caps, not bold
        "name": "markup.smallcaps.tmark",
        "match": r"(?<![\w\\])(__)(?=\S)((?:[^_]|_(?!_))+?)(?<=\S)(__)(?!\w)",
        "captures": {
            "1": {"name": "punctuation.definition.smallcaps.begin.tmark"},
            "2": {"patterns": inline_content()},
            "3": {"name": "punctuation.definition.smallcaps.end.tmark"},
        },
    },
    "code-hilite": {
        # `` `#!py print(1)` ``
        "name": "markup.inline.raw.string.markdown",
        "match": r"(?<!`)(`)(#!)([\w+-]+)[ \t]([^`]*)(`)(?!`)",
        "captures": {
            "1": {"name": "punctuation.definition.raw.markdown"},
            "2": {"name": "keyword.control.shebang.tmark"},
            "3": {"name": "fenced_code.block.language.markdown"},
            "5": {"name": "punctuation.definition.raw.markdown"},
        },
    },
    "progress": {
        # `[=75% "Review"]`
        "name": "meta.progressbar.tmark",
        "match": r'(\[)(=)(\d+(?:\.\d+)?%|\d+/\d+)(?:[ \t]+("[^"]*"))?(\])',
        "captures": {
            "1": {"name": "punctuation.definition.progressbar.begin.tmark"},
            "2": {"name": "keyword.operator.progressbar.tmark"},
            "3": {"name": "constant.numeric.progressbar.tmark"},
            "4": {"name": "string.quoted.double.tmark"},
            "5": {"name": "punctuation.definition.progressbar.end.tmark"},
        },
    },
    "math-inline-compat": {
        # `\( … \)`, the LaTeX habit accepted next to `$ … $`
        "name": "markup.math.inline.markdown",
        "match": r"(\\\()(.+?)(\\\))",
        "captures": {
            "1": {"name": "punctuation.definition.math.begin.markdown"},
            "2": {"name": "meta.embedded.math.markdown", "patterns": [{"include": "text.html.markdown.math#math"}]},
            "3": {"name": "punctuation.definition.math.end.markdown"},
        },
    },
}

HEADER = "Generated by scripts/build_grammar.py from the recognisers of specs/tmark.md. Do not edit by hand."

grammar = {
    "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
    "information_for_contributors": [HEADER],
    "name": "TMark",
    "scopeName": "text.html.markdown.tmark",
    "fileTypes": ["tmark", "tmd"],
    "patterns": [
        {"include": "#block"},
        {"include": "#inline"},
        {"include": "text.html.markdown"},
    ],
    "repository": repository,
}

# Scopes inside which none of the TMark patterns fire: code, front matter, math,
# comments, strings, and the heads of our own constructs (already tokenised).
EXCLUDED = [
    "comment",
    "string",
    "meta.embedded",
    "markup.fenced_code",
    "markup.raw",
    "markup.inline.raw",
    "markup.math",
    "meta.attributes.tmark",
    "meta.role.tmark",          # role content re-includes #inline itself
    "meta.reference",
    "meta.moustache.tmark",
    "meta.directive.head.tmark",
]

injection = {
    "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
    "information_for_contributors": [HEADER],
    "name": "TMark (Markdown injection)",
    "scopeName": "text.html.markdown.tmark.injection",
    "injectionSelector": "L:text.html.markdown - (" + ", ".join(EXCLUDED) + ")",
    "patterns": [
        {"include": "text.html.markdown.tmark#block"},
        {"include": "text.html.markdown.tmark#inline"},
    ],
}


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    SYNTAXES.mkdir(exist_ok=True)
    write(SYNTAXES / "tmark.tmLanguage.json", grammar)
    write(SYNTAXES / "tmark.injection.tmLanguage.json", injection)
