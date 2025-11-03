# texsmith-index

`texsmith-index` provides three coordinated extensions:

- a **Markdown** extension that introduces the syntax `#[tag0][tag1][tag2]{style}` and emits HTML spans annotated with `data-tag` attributes;
- a **TeXSmith** renderer hook that converts those spans into `\index{...}` commands while tracking entries across documents;
- a **MkDocs** plugin that collects discovered tags and injects them into the Material lunr search index.

See the sample project under `packages/texsmith-index/examples/index-demo` for a minimal MkDocs and TeXSmith configuration that enables all three components.
