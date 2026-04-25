# Plain Markdown table caption with inline formatting is silently dropped

## Summary

When a `Table: …` caption line above a plain Markdown table (i.e. not a
` ```yaml table ` fence) contains inline Markdown markers — italics
(`*x*`), inline code (`` `x` ``), links, etc. — the caption is **silently
dropped**: it does not become a `<caption>` element on the table and
instead remains as a plain paragraph in the output (so it renders as body
text in front of the table, unrelated to it).

This is the symmetric counterpart of the yaml-table caption bug fixed in
`extensions/tables/html.py` (use of `_set_inline_content` for the caption
text). The plain-Markdown path has its own preprocessor and treeprocessor
and was not addressed by that fix.

## Reproduction

```markdown
Table: Coverage of the old foundation (*Info1*, *Info2*)

| Skill | Description |
|-------|-------------|
| Foo   | Bar         |
```

After `texsmith --build … article`, the rendered LaTeX contains:

```latex
Table: Coverage of the old foundation (\emph{Info1}, \emph{Info2})

\begin{table}[H]
\centering
\begin{tabular}{ll}
…
\end{tabular}
\end{table}
```

— the `Table: …` line is rendered as a regular paragraph; the caption is
**not** attached to the table at all (no `\caption{…}` is emitted).

The same source without italics works correctly:

```markdown
Table: Coverage of the old foundation

| … |
```

→ produces a proper `\caption{Coverage of the old foundation}` inside the
table environment.

## Root cause

[`_MarkdownTableCaptionTreeprocessor._caption_from_paragraph`](../../src/texsmith/extensions/tables/markdown.py)
early-returns when the paragraph contains any child elements:

```python
@staticmethod
def _caption_from_paragraph(
    paragraph: ElementTree.Element,
) -> _CaptionInfo | None:
    if len(paragraph):
        # Caption paragraphs are expected to be plain text.
        return None
    text = (paragraph.text or "").strip()
    if not text.startswith("Table:"):
        return None
    return _parse_caption_line(text)
```

A paragraph containing `<em>`, `<code>`, `<a>` etc. has
`len(paragraph) > 0`, so the treeprocessor returns `None` and the
paragraph is left in the document. No fallback handles this case —
`_attach_caption` is also written under the assumption that the caption
is plain text (it does `caption.text = info.text`).

## Suggested fix

Two changes:

1. In `_caption_from_paragraph`, do **not** short-circuit on
   `len(paragraph) > 0`. Inspect `paragraph.text` (text before the first
   child) for the `Table:` prefix; if present, return a richer
   `_CaptionInfo` that preserves the paragraph's inline structure.

2. In `_attach_caption`, instead of `caption.text = info.text`, build the
   `<caption>` element by:
   - Setting `caption.text` to the leading text after stripping
     `"Table:"` (and trimming any leading whitespace).
   - Moving the paragraph's children into the new `<caption>` element
     (preserving order).
   - If the existing `_CAPTION_LINE_RE` extracts a `{#label}` suffix,
     that suffix lives in the *trailing tail* of the last child or in
     the leading text when no children exist; we need to detect it on
     whichever node carries it and strip it before moving children.

A clean shape:

```python
@staticmethod
def _caption_from_paragraph(paragraph):
    leading = (paragraph.text or "").lstrip()
    if not leading.startswith("Table:"):
        return None
    # Strip the Table: prefix from the leading text, leaving inline
    # structure intact.
    return _CaptionInfoRich(
        leading=leading[len("Table:"):].lstrip(),
        children=list(paragraph),
        # tail of last child holds the optional {#label} suffix
        trailing=…,
    )
```

`_attach_caption` then becomes a transfer of (leading text, children,
trailing text without `{#label}`) into a fresh `<caption>` element, with
the label peeled off and assigned to `table.set("id", label)` as today.

## Workaround

Use a ` ```yaml table ` fence instead of a plain Markdown table — the
yaml-table preprocessor handles caption italics correctly since the fix
to `extensions/tables/html.py` that wraps caption text through
`_set_inline_content`.

## Out of scope but worth verifying

- Inline code in captions (`` `foo` ``) likely fails the same way. Same
  root cause.
- Inline links (`[text](url)`) probably same.
- Whether the source-line-level capture path used in some other table
  flows has the same blind spot is worth a quick audit while at it.
