import markdown


TEST_MD = r"""
Test [](){index,term1,term2} foobar.
"""

extensions = [
    "markdown.extensions.extra",
    "markdown.extensions.attr_list",
    "markdown.extensions.toc",
    "markdown.extensions.smarty",
    "markdown.extensions.admonition",
    "pymdownx.superfences",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.tasklist",
    "pymdownx.magiclink",
    "pymdownx.details",
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
