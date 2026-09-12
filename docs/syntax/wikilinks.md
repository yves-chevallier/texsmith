# Wiki Links

`[[Page Title]]` belongs to the PyMdownX compatibility profile, not to TMark:
there is no wiki-link node, and the printer never emits the spelling. It is
listed as sugar for a link to the project file of that name.

```md
[[Getting Started]]

[[Subfolder/Page Title|Custom label]]
```

- The portion before the pipe names a Markdown file (`Getting Started` →
  `getting-started.md`).
- Anything after `|` is the link text.

!!! warning "Not implemented yet"
    The parser recognises the spelling and reports `compat-unsupported`: the
    text stays literal rather than becoming a link. Do not rely on it in a
    document meant for print.

The canonical spelling is the link itself, which every renderer understands and
whose broken targets are visible rather than silent:

```md
[Getting Started](getting-started.md)

[Custom label](subfolder/page-title.md)
```

An empty-text link to another file (`[](getting-started.md)`) resolves to that
document's section number in print — see [References](references.md).
