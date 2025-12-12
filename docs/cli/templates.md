# Templates

Templates are pre-defined LaTeX document structures that dictate the overall layout, style, and organization of your final document. TeXSmith includes several built-in templates for common document types, and you can also create and use custom templates.

## Use a template

TeXSmith provides some templates out of the box to help you get started with common document types. You can specify a template using the `--template` (or `-t`) option followed by the template name.

```bash
texsmith document.md --template article
```

## Listing Available Templates

To see the list of available templates, use the `--list-templates` flag:

```text
➜ uv run texsmith --list-templates
                           Available Templates
┌──────────┬─────────┬───────────────────────────────────────────────────┐
│ Name     │ Origin  │ Location                                          │
├──────────┼─────────┼───────────────────────────────────────────────────┤
│ article  │ builtin │ /home/ycr/texsmith/src/texsmith/templates/article │
│ book     │ builtin │ /home/ycr/texsmith/src/texsmith/templates/book    │
│ letter   │ builtin │ /home/ycr/texsmith/src/texsmith/templates/letter  │
│ snippet  │ builtin │ /home/ycr/texsmith/src/texsmith/templates/snippet │
└──────────┴─────────┴───────────────────────────────────────────────────┘
```

Each templates comes with its own set of slots, styles, and configurations tailored for specific document types. For example, the `article` template is suitable for academic papers, while the `book` template is designed for longer documents with chapters and parts.

## Explore Template Details

You can inspect the details of a specific template using the `--template-info` flag. This command provides information about the template's metadata, slots, attributes, and assets.

```bash
texsmith --template article --template-info
```

It will display a summary of the template, including:

- List of attributes and their types (e.g. authors, columns, date, language...)
- List of assets included in the template (e.g. style files, images...)
- List of fragments (`ts-geometry`, `ts-typesetting`, ...) that the template uses.
- List of slots available for content injection.

## Scaffolding Custom Templates

One goal of TeXSmith is to make it easy to create and share custom templates. You can scaffold a new template by copying an existing one and modifying it to suit your needs. Use the `--template-scaffold` flag to copy a template to a local directory:

```bash
texsmith --template article --template-scaffold my-custom-template/
```

Then you can edit the files in `my-custom-template/` to customize the layout, styles, and slots as needed. Then, use your custom template by specifying its path:

```bash
texsmith document.md --template ./my-custom-template/
```
