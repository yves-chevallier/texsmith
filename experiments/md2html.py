import markdown


TEST_MD = r"""

> | Col1 | Col2 |
> | ---- | ---- |
> | Val1 | Val2 |

| Col1 | Col2 |
| ---- | ---- |
| Val1 | Val2 |

"""

extensions = [
    "abbr",
    "admonition",
    "attr_list",
    "def_list",
    "footnotes",
    "markdown.extensions.admonition",
    "markdown.extensions.attr_list",
    "markdown.extensions.extra",
    "markdown.extensions.smarty",
    "markdown.extensions.toc",
    "md_in_html",
    "mdx_math",
    "pymdownx.betterem",
    "pymdownx.blocks.caption",
    "pymdownx.blocks.html",
    "pymdownx.caret",
    "pymdownx.critic",
    "pymdownx.details",
    "pymdownx.emoji",
    "pymdownx.fancylists",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.keys",
    "pymdownx.magiclink",
    "pymdownx.mark",
    "pymdownx.saneheaders",
    "pymdownx.smartsymbols",
    "pymdownx.snippets",
    "pymdownx.superfences",
    "pymdownx.tabbed",
    "pymdownx.tasklist",
    "pymdownx.tilde",
    "tables",
    "texsmith.markdown_extensions.missing_footnotes:MissingFootnotesExtension",
    "toc",
]

extension_configs = {
    "pymdownx.highlight": {"linenums": False},
    "pymdownx.magiclink": {"repo_url_shortener": True},
}

md = markdown.Markdown(
    extensions=extensions,
    extension_configs=extension_configs,
    output_format="html5",
)
body = md.convert(TEST_MD)

print(body)
