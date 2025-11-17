# Scientific Paper

This example shows how TeXSmith can be used to write scientific papers with
Markdown source, bibliographies, and figures.  It uses the `article` template
package, which provides a standard article layout with support for
citations, cross-references, and floating figures/tables.

````markdown
--8<--- "docs/assets/examples/cheese.md"
````

To render the example manually:

```bash
texsmith render cheese.md cheese.bib -tarticle --build
```

The documentation preview uses the default A4 portrait layout. Click the image
to download the PDF.

[![Scientific paper preview](../assets/examples/paper.png){width=70%}](../assets/examples/paper.pdf)
