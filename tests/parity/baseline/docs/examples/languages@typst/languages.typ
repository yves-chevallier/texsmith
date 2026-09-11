#set document(
  title: "Languages",
)
#set page(
  paper: "a4",
  margin: 2.5cm,
  numbering: none,
  footer: context {
    if counter(page).final().first() > 1 {
      align(center)[#counter(page).get().first()]
    }
  },
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
  #text(size: 1.8em, weight: "bold")[Languages]
]
#v(1.5em)

TeXSmith speaks more than Markdown—it speaks your language. Noto fonts ship in, so LaTeX stops tripping over glyphs while browsers casually fall back. Most scripts just work out of the box; typographic nuances for highly specialized scripts (Arabic, Japanese, etc.) can be layered in if or when you need them.

Below, we render a dialect sampler through the `article` template and lay two PDF pages side-by-side (`layout: 2x1`). Click to fetch the PDF.

Source:

```markdown

```

Build it locally:

```bash
texsmith build dialects.md -tarticle --build
```

= Fallbacks

Font fallback is… complicated—almost _passionately_ so. In a browser, the mechanism is straightforward: if a glyph is missing in the first font, the engine walks the font stack and tries the next one, and the next one, until it eventually finds something that contains the character. For obscure Unicode blocks or emoji, Chrome and other modern browsers ultimately fall back to Google’s Noto super-family, which covers most of the Unicode universe.

LaTeX, on the other hand, does *not* provide automatic font fallback in the same way. With classic pdfLaTeX there is no real fallback mechanism at all; if a glyph isn’t in the selected font, you simply get a missing-glyph warning or a tofu box.

LuaLaTeX changes the game: thanks to the `luaotfload` package, it _can_ perform font fallback, but you must explicitly define fallback fonts in your document or template.

However, for this to work, those fallback fonts need to actually _exist_ on your TeX system. And this is where it gets tricky: installing Noto fonts via TeX Live (`tlmgr`) or via system packages like `apt install fonts-noto` is often incomplete, because distributions usually ship only a subset of the full Noto collection. For full Unicode coverage (emoji, rare historical scripts, CJK extensions, etc.), you often need to manually download and install the complete font set from Google’s official Noto Fonts repository.
