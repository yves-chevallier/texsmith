# Research Paper

This example shows how TeXSmith can be used to write scientific papers with
Markdown source, bibliographies, and figures.  It uses the `article` template
package, which provides a standard article layout with support for
citations, cross-references, and floating figures/tables.

The documentation preview uses the default A4 portrait layout. Click the image
to download the PDF.

````md {.snippet data-caption="Download PDF" data-frame="true" data-template="article" data-layout="2x2" data-width="70%" data-files="cheese.bib" data-cwd="../../examples/paper/"}
---8<--- "examples/paper/cheese.md"
````

Here is the source code for this example:

=== "Article"

    ````markdown
    --8<--- "docs/assets/examples/cheese.md"
    ````

=== "Bibliography"

    ```bibtex
    --8<--- "docs/assets/examples/cheese.bib"
    ```

To render the example manually:

```bash
texsmith cheese.md cheese.bib -tarticle --build
```

!!! info

    Naturally, this article isn’t an actual research paper! It’s AI-generated
    content cooked up purely for demo purposes. One reference *is* real, though—the one
    containing the original figure. I don’t own the rights to that figure; I simply
    redrew it in vector form. All author names and the contents of the other references
    are completely fictional. Any resemblance to real people or publications is
    entirely coincidental… unless the cheese overlords say otherwise.

!!! note

    I came up with this example because: (1) as a Swiss person, cheese is basically
    part of my operating system, and (2) when I was a student, a friend of mine did
    his PhD on cheese and collected delightfully absurd cheese-related research that
    nobody would imagine studying scientifically.

    I intially thought about an article on how Swiss music—specifically yodeling—might
    influence cheese ripening. But, well… rheology felt slightly more scientifically
    defensible.

