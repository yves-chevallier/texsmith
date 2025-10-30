import markdown


TEST_MD = r"""

Figure Caption Avec un chocolat violet qui sent la **vanille**  {#foobar}
: ![A duck](duck.jpg){width=25%}

Table Caption Avec une grosse famille de chats  {#bigcats}
: | Cat Name    | Age | Color      |
  | ----------- | ---:| ---------- |
  | Whiskers    |  2  | Tabby      |
  | Mittens     |  5  | Black      |
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
    #"mdx_math",
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
    "pymdownx.arithmatex",
    "tables",
    "toc",
]

from pymdownx.arithmatex import arithmatex_fenced_format

extension_configs = {
    "pymdownx.highlight": {"linenums": False},
    "pymdownx.magiclink": {"repo_url_shortener": True},
    "pymdownx.superfences": {
        "custom_fences": [
            {
                "name": "math",
                "class": "arithmatex",
                "format": arithmatex_fenced_format,  # <— ici !
            }
        ]
    }
}

md = markdown.Markdown(
    extensions=extensions,
    extension_configs=extension_configs,
    output_format="html5",
)
body = md.convert(TEST_MD)

print(body)
