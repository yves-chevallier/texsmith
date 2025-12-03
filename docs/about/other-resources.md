# Other Similar Projects

Here are some other projects and tools that are related to TeXSmith in terms of functionality, purpose or target audience.

## Converters and Parsers

[Pandoc](https://pandoc.org/)
: A universal document converter that supports a wide range of formats, including Markdown, LaTeX, HTML, and more. Written in Haskell not ready for smooth integration with Python projects. Very extensible, but may require effort to set up custom conversions, filters, and adapt templates.

[kramdown](https://kramdown.gettalong.org/)
: A fast, pure Ruby Markdown parser that supports a wide range of extensions and features. It is the default Markdown engine for Jekyll. Highly customizable and feature-rich, but primarily geared towards Ruby developers.

[MultiMarkdown](https://fletcherpenney.net/multimarkdown/)
: An extended version of Markdown that adds support for tables, footnotes, citations, and more. It is designed for writers who need more advanced features while maintaining Markdown's simplicity. More powerful than standard Markdown, but with additional syntax to learn.

## Online Editors and Platforms

[Overleaf](https://www.overleaf.com/)
: The leading online LaTeX editor, offering real-time collaboration and a rich set of templates. While primarily focused on LaTeX, it provides some support for Markdown through conversion tools. It is a commercial platform with free and paid plans. Numerous templates and collaboration features, but limited direct Markdown support. A good knowledge of LaTeX is often required.

[Authorea](https://www.authorea.com/)
: An online platform for writing and publishing scientific documents. It supports Markdown, LaTeX, and other formats, with a focus on academic writing. It offers collaboration features and integration with reference management tools. Designed for researchers and academics, but may not be ideal for general-purpose document creation. The WYSIWYG editor is user-friendly, but advanced formatting may be tricky. No direct support for glossary or index generation.

[ShareLaTeX](https://www.sharelatex.com/)
: An online LaTeX editor that allows for real-time collaboration. It has merged with Overleaf, so users are directed to use Overleaf for new projects. Primarily focused on LaTeX, with limited Markdown support through conversion. Strong LaTeX capabilities, but not ideal for Markdown-centric workflows.

[Curvenote](https://curvenote.com/)
: A collaborative platform for writing scientific documents, supporting Markdown and Jupyter Notebooks. It offers real-time collaboration, version control, and integration with data sources. Tailored for scientific writing, but may not cover all general document needs. Good for integrating code and data, but may lack advanced formatting features. It is based on MyST Markdown. The WYSIWYG editor is très aboutit.

[Typora](https://typora.io/)
: A popular Markdown editor that provides a seamless live preview experience. It supports various Markdown flavors and offers a clean, distraction-free interface. While it excels as an editor, it lacks advanced document structuring features like glossary or index generation. Great for writing and note-taking, but not a full-fledged document processor.

## Other structured document formats

[AsciiDoc](https://asciidoc.org/)
: A text document format for writing notes, documentation, articles, books, ebooks, slideshows, web pages, and blogs. It is human-readable and can be converted to HTML, PDF, and other formats. More powerful than Markdown in terms of features and flexibility, but with a steeper learning curve.

[reStructuredText](https://docutils.sourceforge.io/rst.html)
: A file format for textual data used primarily in the Python programming community for technical documentation. It is part of the Docutils project and can be converted to various output formats, including HTML and LaTeX. More complex than Markdown, with a focus on technical documentation. Le langage reST est plus verbeux que Markdown, mais offre des fonctionnalités avancées pour la documentation technique, il est de moins en moins utilisé en faveur de Markdown.

[LaTeX](https://www.latex-project.org/)
: A high-quality typesetting system commonly used for technical and scientific documents. It provides extensive control over document layout and formatting, making it suitable for complex documents. Steeper learning curve compared to Markdown, but offers unparalleled typesetting capabilities.

[DocBook](https://docbook.org/)
: An XML-based markup language for technical documentation. It is designed to be both human-readable and machine-processable, allowing for the creation of structured documents that can be transformed into various output formats. More complex than Markdown, with a focus on technical documentation.

## Static site generator tools

[Sphinx](https://www.sphinx-doc.org/en/master/)
: A documentation generator primarily used for Python projects. It supports reStructuredText and Markdown (with extensions) and can produce HTML, LaTeX, PDF, and other formats. Highly extensible with a wide range of plugins and themes, but primarily geared towards technical documentation.

[Jekyll](https://jekyllrb.com/)
: A popular static site generator that transforms plain text into static websites and blogs. It supports Markdown and Liquid templating. Widely used for GitHub Pages, with a large community and many themes available. Simple to set up, but may require knowledge of Ruby for advanced customization.

[Hugo](https://gohugo.io/)
: A fast and flexible static site generator written in Go. It supports Markdown and offers a variety of themes and plugins. Known for its speed and ease of use, making it suitable for both beginners and advanced users. Extensive documentation and a strong community.

[MkDocs](https://www.mkdocs.org/)
: A static site generator focused on project documentation. It uses Markdown for content and YAML for configuration. Easy to set up and use, with a variety of themes available. Ideal for creating simple, clean documentation sites.

[Zensical](https://www.zensical.com/)
: A modern static site generator that emphasizes simplicity and speed. It supports Markdown and offers a range of themes. Designed for quick setup and deployment, making it suitable for personal blogs and small websites. A next gen MkDocs Material alternative.

[Gatsby](https://www.gatsbyjs.com/)
: A React-based static site generator that allows for building fast and modern websites. It supports Markdown and offers a rich ecosystem of plugins and themes. Ideal for developers familiar with React, but may have a steeper learning curve for beginners.

[Docusaurus](https://docusaurus.io/)
: A static site generator designed for building documentation websites. It supports Markdown and offers features like versioning and localization. Backed by Facebook, it has a strong community and is easy to set up for documentation projects.

[TypeDoc](https://typedoc.org/)
: A documentation generator for TypeScript projects. It uses TypeScript's type information to generate API documentation in Markdown or HTML format. Ideal for TypeScript developers looking to document their codebases.

[Hexo](https://hexo.io/)
: A fast, simple, and powerful blog framework powered by Node.js. It uses Markdown for content creation and offers a variety of themes and plugins. Known for its speed and ease of use, making it suitable for bloggers and developers alike.

[Pelican](https://blog.getpelican.com/)
: A static site generator written in Python that uses Markdown and reStructuredText for content. It offers a range of themes and plugins, making it flexible for various types of websites. Ideal for Python developers looking for a static site solution.

[Zola](https://www.getzola.org/)
: A fast static site generator in a single binary with everything built-in. It uses Markdown for content and offers a variety of themes. Known for its speed and simplicity, making it easy to set up and deploy websites.

## Markdown Syntaxes

[CommonMark](https://commonmark.org/)
: A strongly defined, highly compatible specification of Markdown. It aims to standardize Markdown syntax and behavior across different implementations. Very limited in features compared to other Markdown flavors, focusing on core syntax for maximum compatibility.

[GitHub Flavored Markdown (GFM)](https://github.github.com/gfm/)
: An extension of CommonMark used by GitHub, adding features like tables, task lists, and strikethrough. Widely used in the developer community, especially for README files and documentation on GitHub. More feature-rich than CommonMark, but still focused on simplicity and compatibility.

[Pandoc Markdown](https://pandoc.org/MANUAL.html#pandocs-markdown)
: A Markdown flavor used by the Pandoc document converter, supporting a wide range of extensions and features. It is highly flexible and can be customized for various output formats. Very feature-rich, but may be overwhelming for users looking for a simple Markdown experience.

[Markdown Extra](https://michelf.ca/projects/php-markdown/extra/)
: An extension of the original Markdown syntax that adds features like tables, footnotes, and definition lists. It is designed to enhance Markdown's capabilities while remaining easy to read and write. More features than standard Markdown, but still user-friendly. Used on PHP-based platforms like WordPress.

[MyST Markdown](https://myst-parser.readthedocs.io/en/latest/)
: A Markdown flavor designed for technical documentation, supporting directives and roles similar to reStructuredText. It is used in Sphinx and Jupyter Book for creating complex documents. Very powerful for technical writing, but with a steeper learning curve due to additional syntax.

[MDX](https://mdxjs.com/)
: A Markdown flavor that allows embedding JSX components within Markdown files. It is commonly used in React-based projects to create interactive documentation and blogs. Highly flexible for React developers, but requires knowledge of JSX and React.

[Pymdown](https://pymdown.github.io/)
: A set of extensions for Python Markdown that adds various features and enhancements. It includes support for tables, footnotes, and more. Designed to work seamlessly with Python Markdown, making it suitable for Python projects. Offers additional functionality while maintaining compatibility with standard Markdown.

## Markdown parsers

[Python Markdown](https://python-markdown.github.io/)
: A popular Markdown parser for Python, supporting various extensions and features. It is easy to use and integrates well with Python projects. Highly extensible, making it suitable for developers looking to customize their Markdown processing. Used in MkDocs and other Python-based tools.

[Markdown-it](https://markdown-it.github.io/)
: A flexible and extensible Markdown parser for JavaScript. It supports a wide range of plugins and can be customized to fit various needs. Highly configurable, making it suitable for developers looking to tailor their Markdown processing.

[Marked](https://marked.js.org/)
: A fast, lightweight Markdown parser and compiler for JavaScript. It supports a variety of extensions and is designed for performance. Suitable for web applications that require quick Markdown processing.

[Remarkable](https://github.com/jonschlinkert/remarkable)
: A Markdown parser for JavaScript that supports various extensions and plugins. It is designed to be fast and flexible, allowing developers to customize their Markdown processing. Highly extensible, making it suitable for developers looking to tailor their Markdown experience.

## Diagramming Tools (online editors)

[Mermaid](https://mermaid-js.github.io/mermaid/#/)
: A popular diagramming and charting tool that uses a simple Markdown-like syntax to create diagrams. It supports flowcharts, sequence diagrams, Gantt charts, and more. Easily integrable with various platforms and tools, making it a favorite among developers and technical writers.

[Draw.io](https://app.diagrams.net/)
: A free online diagramming tool that supports a wide range of diagram types, including flowcharts, UML diagrams, network diagrams, and more. It offers a user-friendly interface and integrates with various cloud storage services. Versatile and easy to use, making it suitable for both casual and professional users.

[Graphviz](https://graphviz.org/)
: An open-source graph visualization software that uses the DOT language to describe graphs. It is widely used for creating complex diagrams and visualizations. Highly customizable, but may have a steeper learning curve due to its syntax.

[PlantUML](https://plantuml.com/)
: A tool that allows users to create UML diagrams from plain text descriptions. It supports various diagram types, including class diagrams, sequence diagrams, and use case diagrams. Popular among software developers for documenting system designs.

[Ditaa](http://ditaa.sourceforge.net/)
: A small command-line tool that converts ASCII art diagrams into proper bitmap graphics. It is useful for creating simple diagrams quickly without the need for complex software. Lightweight and easy to use, but limited in features compared to other diagramming tools.

[SVGBob](https://ivanceras.github.io/svgbob-editor/)
: A tool that converts ASCII art diagrams into SVG graphics. It is designed to be simple and easy to use, making it suitable for quick diagram creation. Lightweight and focused on SVG output, but may lack advanced features found in other tools.

[BlockDiag](http://blockdiag.com/en/blockdiag/index.html)
: A set of tools that generate block diagrams from simple text descriptions. It supports various diagram types, including block diagrams, sequence diagrams, and activity diagrams. Useful for creating structured diagrams quickly, but may have limited customization options.

[BPMN](https://demo.bpmn.io/new)
: An online tool for creating Business Process Model and Notation (BPMN) diagrams. It provides a user-friendly interface for designing business processes and workflows. Specifically focused on BPMN, making it ideal for business analysts and process designers. Can be exported in XML format for further processing.

[Pikchr](https://pikchr.org/)
: A simple diagramming tool that uses a text-based syntax to create diagrams. It is designed to be easy to learn and use, making it suitable for quick diagram creation. Lightweight and straightforward, but may lack advanced features found in other diagramming tools.

[TikZ](https://tikz.dev/)
: A powerful LaTeX package for creating high-quality graphics programmatically. It is widely used in academic and scientific documents for creating complex diagrams and illustrations. Highly customizable, but requires knowledge of LaTeX and a steeper learning curve.

[WaveDrom](https://wavedrom.com/)
: An online tool for creating digital timing diagrams from a simple text-based description. It is useful for visualizing digital signals and timing relationships. Focused on timing diagrams, making it ideal for hardware designers and engineers.

[Kroki](https://kroki.io/)
: A service that allows users to create diagrams from various text-based formats, including PlantUML, Mermaid, Graphviz, and more. It provides an easy way to generate diagrams without installing software locally. Supports a wide range of diagram types, making it versatile for different use cases.
