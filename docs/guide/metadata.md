# Metadata Conventions

TeXSmith normalizes a handful of common front matter fields so that templates and fragments can lean on a single canonical name. External configuration files, CLI `--attribute` overrides, and Markdown `press.*` blocks are all merged into one flat namespace before the template resolver runs, so manifests can simply reference the final attribute (e.g. `emoji`, `glossary_style`, `width`) without worrying about where it originally came from. The full `press` tree is still kept around for backwards compatibility, but no other part of the codebase needs to dig through dotted `press.*` paths anymore.

## Title & Subtitle

`title` and `subtitle` do exactly what the tin says: declare them in the front matter and they become the document's title and subtitle inside the template.

`title` is not strictly required. If omitted, TeXSmith falls back to the first heading in the document, on the assumption that you probably meant *that* to be the title. To opt out of this fallback (and render with no title at all), set `title: null` explicitly:

```md
---
subtitle: "An In-depth Exploration"
---
# This section heading will not be used as the title
```

```md
---
title: Some Title
---
# This section heading will not be used as the title
```

## Authors

Author metadata is validated with Pydantic and normalized into a list of objects shaped like `{ name, affiliation }`. The parser is forgiving on input, several syntaxes are accepted, all of which collapse to the same canonical structure:

```yaml
---
authors: "Ada Lovelace"
---
```

```yaml
---
authors:
  - "Ada Lovelace"
  - "Grace Hopper"
---
```

```yaml
---
authors:
  - name: Ada Lovelace
    affiliation: Analytical Engine
  - name: Grace Hopper
    affiliation: US Navy
---
```

```yaml
---
authors:
  name: Ada Lovelace
  affiliation: Analytical Engine
---
```

Each entry is trimmed, validated, and stored as `{ "name": ..., "affiliation": ... }`. A missing `name` is a hard error: TeXSmith bails out before the template render even starts, so you never end up with a half-credited document.

The legacy singular `author` key is still understood by the parser for backwards compatibility, but the plural `authors` is the canonical form, prefer it whenever you can.

## Date

The `date` field is parsed into a real `datetime` object, which means templates can apply the `date` filter to format it however they please. Several input shapes are accepted:

```yaml
---
date: 2024-07-01 # ISO format
date: "Custom date string"
date:
  year: 2024
  month: 7
  day: 1
date: commit
```

The special `commit` value resolves to the date of the most recent Git commit touching the document, perfect for stamping a "last updated" date without ever editing it by hand.

Once rendered, the date is formatted according to the template's locale. `2024-07-01` lands as "July 1, 2024" in an English template, or "1 de julio de 2024" in a Spanish one. LaTeX (with a little help from `babel`) handles the linguistic gymnastics.

## Version

The `version` field is a free-form label describing where the document sits in its lifecycle. It is intentionally unopinionated, anything goes: semver, calendar versioning, a Git ref, or a human-readable tag like "Confidential Draft".

```yaml
---
version: Confidential Draft # Arbitrary string
version: 1.0.0 # Semver format
version:
  major: 1
  minor: 0
  patch: 0
version: git
```

The special `git` value resolves to the latest Git tag (falling back to a short commit hash if no tag exists), giving you automatic, repository-driven versioning with zero manual upkeep.

## Fragments' Metadata

Fragments, the small, composable extensions that plug into a LaTeX template, can declare their own metadata schema in a `fragment.toml` file. Their attributes get merged into the same flat namespace as everything else, so a fragment-defined key looks no different from a built-in one at render time. See the [Fragment Guide](fragments/index.md) for the full declaration syntax and resolution rules.
