# Structured glossary

This example demonstrates the structured `glossary:` front-matter section in
TeXSmith. Each acronym carries a description and an optional group; TeXSmith
emits one localised `\printglossary` table per group (in declaration order),
plus a default table for ungrouped entries. The legacy `*[KEY]: …` body
syntax keeps working and merges with the front-matter entries.

```bash
make           # build with lualatex
```
