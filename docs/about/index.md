# About

TeXSmith was originally created by Yves Chevallier in 2025 to address the need for a seamless workflow between Markdown-based documentation and LaTeX-based publishing, initially for his own academic [courses](https://heig-tin-info.github.io/handbook/) at HEIG-VD.

Aside from Pandoc—written in Haskell and not directly suited for MkDocs—there were no tools capable of converting MkDocs-flavored Markdown into LaTeX while preserving the original content’s semantic intent.

Because developing such an ambitious toolchain was a substantial and time-consuming effort, I postponed the project until I discovered the remarkable power of OpenAI Codex, which helped me bootstrap the initial version of TeXSmith in just a few days. I wanted to extract the core MkDocs-to-LaTeX code used in my online course and turn it into a standalone, general-purpose tool that anyone needing to convert MkDocs content to LaTeX could use. That is how TeXSmith was born.
