# About

TeXSmith was originally created by Yves Chevallier in 2025 to address the need for a seamless workflow between Markdown-based documentation and LaTeX-based publishing, initially for his own academic [courses](https://heig-tin-info.github.io/handbook/) at HEIG-VD.

Aside from [Pandoc](https://pandoc.org/) -- written in [Haskell](https://en.wikipedia.org/wiki/Haskell) and not directly suited for [MkDocs](https://www.mkdocs.org/) -- there were no tools capable of converting MkDocs-flavored Markdown into LaTeX while preserving the original content’s semantic intent.

Because developing such an ambitious toolchain was a substantial and time-consuming effort, I postponed the project until I discovered the remarkable power of OpenAI Codex, which helped me bootstrap the initial version of TeXSmith in just a few days. I wanted to extract the core MkDocs-to-LaTeX code used in my online course and turn it into a standalone, general-purpose tool that anyone needing to convert MkDocs content to LaTeX could use. That is how TeXSmith was born.

## Branding

This project is **not affiliated with TeX, LaTeX, or the LaTeX Project**. It merely produces LaTeX-compatible output and interacts with the TeX toolchain in the same way any document-generation utility would. All trademarks belong to their respective owners.

By convention within the TeX community, the names *TeX* and *LaTeX* are used with care. [Donald Knuth](https://en.wikipedia.org/wiki/Donald_Knuth) famously stated:

> **“TeX is not to be changed; only Knuth himself may change TeX.”**

This is not a legal trademark declaration but a long-standing cultural rule: any system that calls itself *TeX* must be fully compatible with Knuth’s canonical implementation. Similarly, the LaTeX Project requires that only implementations conforming to the LaTeX format may use the name *LaTeX*.

In keeping with these established norms, this project does **not** claim to be a TeX or LaTeX implementation, nor does it modify or replace them. It is simply a tool that *generates* LaTeX code as output, leaving the actual typesetting to standard, community-maintained engines.
