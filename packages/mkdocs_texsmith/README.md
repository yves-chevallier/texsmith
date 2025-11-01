# MkDocs TeXSmith Plugin

`mkdocs-texsmith` turns any MkDocs project into a set of LaTeX sources ready for high-quality PDF production. The plugin reuses the TeXSmith rendering pipeline to transform the pages that MkDocs renders into TeX, keeping navigation structure, numbering, cross references, and assets in sync.

## Highlights

- Export one or many "books" from the same MkDocs site, each with its own metadata and output folder.
- Reuse TeXSmith templates or override individual blocks to match your house style.
- Combine global `.bib` files, per-book bibliographies, inline citations, and DOI lookups into a single bibliography.
- Copy and prune assets automatically so only referenced images end up in the LaTeX project.
- Optional HTML snapshots for debugging, plus Material for MkDocs specific tweaks out of the box.

## Installation

```bash
pip install mkdocs-texsmith
```

The package targets Python 3.12+. If you manage dependencies with [uv](https://github.com/astral-sh/uv), run:

```bash
uv add mkdocs-texsmith
```

## Quick Start

1. Add the plugin to your `mkdocs.yml`.

   ```yaml
   plugins:
     - search
     - texsmith:
         build_dir: press # where LaTeX sources are written
         template: book # TeXSmith template to use
         bibliography:
           - docs/references.bib
   ```

2. Build your site as usual:

   ```bash
   mkdocs build
   ```

3. The LaTeX project for each configured book is created under `press/`. Compile the resulting `index.tex` with your preferred tool (`latexmk`, `tectonic`, etc.) to produce the PDF.

## Configuration

All plugin options are declared under the `texsmith` plugin entry.

- `enabled` (bool): turns the plugin on or off; automatically disabled during `mkdocs serve`.
- `build_dir` (str): output root for generated LaTeX projects. Defaults to `press`.
- `template` (str): default TeXSmith template name. Falls back to `book`.
- `parser` (str): HTML parser backend used by TeXSmith (`lxml` by default).
- `copy_assets` (bool): copy images and other assets referenced by the book into the build directory.
- `clean_assets` (bool): remove unused files from the generated `assets/` folder after rendering.
- `save_html` (bool): if `true`, store the rendered HTML alongside LaTeX snapshots under `html/`.
- `language` (str): override auto-detected language for templates and hyphenation.
- `bibliography` (list[str]): global `.bib` files applied to every book.
- `books` (list[dict]): per-book configuration (see below).
- `template_overrides` (dict[str, str]): map of template block names to override files.
- `register_material` (bool): register Material for MkDocs specific renderers (enabled by default).

### Multiple books

The `books` list lets you export distinct artefacts from the same site. Each entry accepts [`BookConfig`](../../src/texsmith/core/config.py) fields plus book-specific extras (`template`, `template_overrides`, `bibliography`):

```yaml
plugins:
  - texsmith:
      books:
        - title: "User Guide"
          root: "Guide"
          folder: "user-guide"
          template: book
          bibliography:
            - docs/guide.bib
        - title: "API Reference"
          root: "Reference"
          base_level: 2
          copy_files:
            docs/appendix/*.tex: backmatter/
```

If you do not declare any books, the plugin creates one automatically using the first navigation page as the root section.

### Bibliography sources

- Global `bibliography` files apply to every book.
- Book-level `bibliography` entries augment or override the global list.
- YAML front matter can declare inline bibliography entries, including DOI links. DOIs are resolved at build time; failures are logged but do not stop the build.
- Per-book `.bib` files are emitted with the LaTeX project, and an `assets_map.yml` manifest records the asset locations used by the renderer.

### Templates and overrides

TeXSmith templates bundle LaTeX, Jinja, and formatter fragments. Set `template` globally or per book, then override specific fragments via `template_overrides`:

```yaml
plugins:
  - texsmith:
      template: book
      template_overrides:
        heading: overrides/heading.j2
      books:
        - title: "Whitepaper"
          template_overrides:
            cover: overrides/custom_cover.tex.j2
```

The plugin automatically registers TeXSmith's Material integration when `register_material` is `true`, aligning colors and fonts with the Material theme if you use it.

### Assets and HTML snapshots

- `copy_assets: true` copies images and other referenced files into `<build_dir>/<book>/assets/`.
- `clean_assets: true` prunes unused files after rendering, keeping the LaTeX project tidy.
- Enable `save_html` to keep the intermediate HTML for each page under `<build_dir>/<book>/html/`, which helps when troubleshooting rendering issues.

## Development

1. Clone the repository and install dependencies:

   ```bash
   uv sync
   ```

2. Run the documentation site locally:

   ```bash
   uv run mkdocs serve
   ```

3. Use `pytest` or `uv run pytest` to execute tests before contributing patches.

The repository maintains a `Makefile` shortcut (`make deps`) that mirrors the `uv sync` step.

## License

The project is distributed under the MIT License. See `LICENSE.md` for the full text.
