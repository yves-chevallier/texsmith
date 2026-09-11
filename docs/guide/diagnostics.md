# Diagnostics

TeXSmith reports what it could not do well — a missing image, a
cross-reference nobody publishes, a counter defined twice — as
**diagnostics**: one line each, in the shape the `tmark` toolchain prints, so a
finding reads the same whether Python or the Rust core found it.

## What a line looks like

```
report.md:12:5: warning ref-unresolved: Counter reference '@n:missing' has no matching item
```

| Part | Meaning |
| --- | --- |
| `report.md` | the file the finding belongs to |
| `12:5` | 1-based line and 1-based **byte** column of the construct (`tmark check` prints the same numbers) |
| `warning` | the severity |
| `ref-unresolved` | a stable kebab-case code; grep for it, filter on it in CI |
| the rest | one sentence naming the construct |

A finding without a position prints the file name only
(`report.md: warning crossref-inventory-missing: …`), and a message that has no
file — an engine or network failure — prints as `warning texsmith: …`.

With `-v`, a suggested fix and the related locations (the other definition of
a duplicate key) follow, indented under the line.

## Severities

| Severity | Meaning | `--strict` |
| --- | --- | --- |
| `hint` | a style nit; nothing is wrong with the output | ignored |
| `info` | something was done on your behalf (a root key overriding `press`) | ignored |
| `warning` | the output has a visible defect (`[?key]`, an empty number, a missing image) | fails |
| `error` | a stage could not complete; the run usually stops | fails |

Warnings and errors are always shown. `-q` hides hints and info lines (they
stay in the JSON dump and in the counts).

When at least one warning or error was recorded, the run ends with a summary:

```
0 errors, 2 warnings
```

## `--strict`

```sh
texsmith report.md --build --strict
```

`--strict` exits with status 1 when any warning or error was recorded. The
check runs **after the LaTeX is written and before the engine runs**, so the
`.tex` is there to inspect and no PDF is produced from a document with a known
hole. The same switch lives in the front matter, for documents that must never
ship with an unresolved reference:

```yaml
press:
  features:
    strict: true
```

`--strict` replaces the former `PYTHONWARNINGS=error`: these findings are no
longer Python warnings and that variable no longer promotes them.

## `--diagnostics-json`

```sh
texsmith report.md --diagnostics-json build/diagnostics.json
```

writes every recorded diagnostic as a JSON list, sorted by file and position,
for editors and CI:

```json
[
  {
    "code": "ref-unresolved",
    "severity": "warning",
    "span": [0, 244, 254],
    "message": "Counter reference '@n:missing' has no matching item",
    "origin": "texsmith",
    "path": "report.md",
    "line": 12,
    "col": 5
  }
]
```

`code`, `severity`, `span` (`[file, start, end]` in bytes), `message` and the
optional `fix` / `related` are tmark's fields; `origin` says which tool found
it (`texsmith` or `tmark`); `path`, `line` and `col` are the printed location,
`null` when the record has none.

## Codes

The codes TeXSmith emits itself are listed in `texsmith.diagnostics.codes`
with their default severity; a few reuse tmark's identifiers on purpose
(`ref-unresolved`, `label-duplicate`, `crossref-inventory-missing`,
`crossref-inventory-stale`, `include-missing`, `deprecated-frontmatter-key`)
because the finding is the one tmark reports once that stage runs in Rust.
The free-form `texsmith` code carries the messages that predate the codes.
