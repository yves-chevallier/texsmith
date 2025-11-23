# Languages

TeXSmith speaks more than Markdown—it speaks your language. Noto fonts ship in, so LaTeX stops tripping over glyphs while browsers casually fall back. Most scripts just work out of the box; typographic nuances for highly specialised scripts (Arabic, Japanese, etc.) can be layered in if/when you need them.

Below, we render a dialect sampler through the `article` template, lay two PDF pages side-by-side (`data-layout="2x1"`), and keep the dog-ear frame enabled. Click to fetch the PDF.

````md {.snippet data-caption="Download PDF" data-title="frontmatter" data-layout="2x1" data-template="article" data-frame="true" data-width="80%"}
---8<--- "examples/dialects/dialects.md"
````

Source:

```markdown
--8<--- "examples/dialects/dialects.md"
```

Build it locally:

```bash
texsmith build dialects.md -tarticle --build
```
