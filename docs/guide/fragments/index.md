# Fragments

Template Fragments are reusable pieces of configuration or content that can be included in multiple documents. They help maintain consistency and reduce redundancy across templates.

A fragment is defined as:

- LaTeX Jinja files that define the fragment structure.
- Python files that provide additional logic or functionality for the fragment.
- Injection points in templates where fragments can be included.

## Builtin fragments

TeXSmith comes with several builtin fragments that can be used out of the box. Some of the commonly used fragments include. For the simple user, this is transparent and does not require any special knowledge.

`ts-geometry`
: Manages page geometry settings using the LaTeX `geometry` package. You can configure page size, margins, and other layout options such as watermarks.

`ts-fonts`
: Handles font settings using the LaTeX `fontspec` package. It allows you to set main fonts, sans-serif fonts, monospaced fonts, and configure font features like ligatures. It provide the fallback mechanism for XeLaTeX and LuaLaTeX engines that allows finding suitable fonts on foreign systems.

`ts-glossary`
: Provides support for glossaries and acronyms using the LaTeX `glossaries` package. It enables the creation and management of glossaries, lists of acronyms, and symbols in documents.

`ts-index`
: Implements index generation using the LaTeX `makeidx` package. It allows you to create and manage indexes in your documents, including support for multiple indexes and custom formatting. This is the way of rendering [indexes][Indexes] in TeXSmith.

`ts-callouts`
: Implements callout boxes using the LaTeX `tcolorbox` package. It allows you to create visually distinct callout boxes for notes, warnings, tips, and other important information. This is the way of rendering [admonitions][Admonitions] in TeXSmith.
