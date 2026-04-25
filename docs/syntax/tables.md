# Tables

Markdown pipe tables are cute until they meet real reports. The minute you
need grouped headers, wrapped text, row spans, totals, or a table that behaves
properly in LaTeX, plain Markdown turns into duct tape. TeXSmith keeps the
simple syntax for simple tables and adds a declarative `yaml table` fence for
the serious stuff.

Use the right level of power:

- Plain Markdown table: quick two-dimensional data, no layout drama.
- Plain Markdown table + `yaml table-config`: keep the pipe table, add LaTeX
  layout metadata.
- `yaml table`: describe the whole table as structured data when spans,
  grouped headers, footers, or validation matter.

## Captions and Labels

Put the standard TeXSmith caption line directly before the table:

````markdown
Table: Fruit stock by warehouse {#tbl:stock}

```yaml table
columns: [Fruit, Geneva, Zurich, Basel]
rows:
  - [Apples,   120, 180, 90]
  - [Pears,    45,  ~,   110]
```
````

The `{#tbl:stock}` part becomes the LaTeX `\label{tbl:stock}` and can be
referenced like any other table. The caption line also works before plain
Markdown tables.

## Full YAML Tables

A full YAML table is a fenced code block whose info string is exactly
`yaml table`:

````markdown
```yaml table
columns: [Fruit, Geneva, Zurich, Basel]
rows:
  - [Apples,   120, 180, 90]
  - [Pears,    45,  ~,   110]
  - separator: {label: Seasonal shortage}
  - [Apricots, 5,   0,   12]
footer:
  - [Total, 170, 180, 212]
```
````

Top-level keys:

| Key       | Purpose |
| --------- | ------- |
| `table`   | Optional table-level settings: width, placement, long-table mode. |
| `columns` | Required column tree. Needs at least two leaf columns. |
| `rows`    | Body rows and separators. |
| `footer`  | Summary rows rendered after an extra rule. |

The first column is the row-label column. In positional rows, the first item
becomes that label and the remaining items fill the data columns.

`~` is YAML null. In normal cells it renders as empty. In span rectangles it
is also the explicit “this slot is absorbed” marker, so the validator knows
you meant it.

## Columns

The short form is just a list of names:

```yaml
columns: [Article, Editor, Status, Pages]
```

For metadata, use mappings:

```yaml
columns:
  - name: Requirement
    width: 25%
    align: l
  - name: Description
    align: justify
  - name: Priority
    width: 15%
    align: center
```

Column attributes:

| Attribute     | Values |
| ------------- | ------ |
| `align`       | `l`, `c`, `r`, `j`, or long forms: `left`, `center`, `centre`, `right`, `justify`, `justified`. |
| `width`       | `auto`, `X`, a percentage such as `25%`, or a raw LaTeX length such as `3cm`. |
| `width-group` | Any identifier. Columns with the same group share the same width. |

Grouped columns are recursive:

```yaml
columns:
  - Product
  - name: FY23
    columns: [Q1, Q2, Q3, Q4]
    width-group: quarter
  - name: FY24
    columns: [Q1, Q2, Q3, Q4]
    width-group: quarter
```

Groups can carry `align`, `width`, and `width-group`; those attributes
propagate to their leaf columns unless a child overrides them. Nested groups
produce multiple header rows and `\cmidrule` strokes in LaTeX.

## Rows

The most compact form is positional:

```yaml
rows:
  - [Apples, 120, 180, 90]
  - [Pears,  45,  ~,   110]
```

For grouped columns, a list cell fills the leaves of that group:

```yaml
columns:
  - Product
  - name: FY24
    columns: [Q1, Q2, Q3, Q4]
rows:
  - [Apples, [130, 145, 160, 150]]
```

Named-row mode trades brevity for typo detection. The row maps data by
top-level column name, and missing columns render empty:

```yaml
columns:
  - Product
  - name: FY23
    columns: [Q1, Q2, Q3, Q4]
  - name: FY24
    columns: [Q1, Q2, Q3, Q4]
rows:
  - Apples:  {FY23: [120, 135, 150, 140], FY24: [130, 145, 160, 150]}
  - label: Cherries
    cells: {FY23: [~, ~, 45, 0]}
```

If you misspell `FY23`, TeXSmith fails locally with an inline table error
instead of silently producing a broken PDF.

## Separators and Footers

A separator inserts a horizontal rule. It can also label a body section:

```yaml
rows:
  - [Apples, 120, 180, 90]
  - separator: {label: Seasonal shortage}
  - [Apricots, 5, 0, 12]
footer:
  - [Total, 125, 180, 102]
```

Equivalent separator forms:

```yaml
- separator: true
- separator:
    label: Seasonal shortage
- separator:
    label: Grand totals
    double-rule: true
```

Footer rows use the same row syntax as body rows.

## Rich Cells and Spans

A scalar cell is enough most of the time. When you need spans or a local
alignment override, promote the cell to a mapping:

```yaml
{value: Maria, rows: 2}
{value: "$570k", cols: 4, align: c}
{value: "Merged 2x3", rows: 2, cols: 3, align: center}
```

Row spans require the absorbed cells below to be `~`:

````markdown
Table: Article assignments {#tbl:articles}

```yaml table
columns: [Article, Editor, Status, Pages]
rows:
  - [Alpha, {value: Maria, rows: 2}, Draft,     12]
  - [Beta,  ~,                        Review,   18]
  - [Gamma, John,                     Published, 24]
```
````

Column spans consume consecutive leaf columns:

````markdown
Table: Annual totals across all four quarters

```yaml table
columns:
  - Metric
  - name: 2024
    columns: [Q1, Q2, Q3, Q4]
rows:
  - [Revenue, [120, 130, 150, 170]]
  - [Cost,    [80,  85,  90,  95]]
  - separator: true
  - [Gross,   {value: "$570k", cols: 4, align: c}]
```
````

A cell can span a rectangle. Every absorbed slot must be acknowledged:

```yaml
columns: [A, B, C, D]
rows:
  - [r1, {value: "Merged 2x3", rows: 2, cols: 3, align: c}]
  - [r2, ~,                                                 ~, ~]
  - [r3, x, y, z]
```

## Widths and LaTeX Environments

By default, `table.width` is `auto`, which selects a natural-width `tabular`
unless a column asks for flexible width. Setting a table width usually selects
`tabularx`:

```yaml
table:
  width: 90%
columns:
  - name: Requirement
    width: 25%
    align: left
  - name: Description
    align: justify
  - name: Priority
    width: 15%
    align: center
```

Width rules:

- `table.width: auto` means natural table width.
- `table.width: 100%` means `\linewidth`; other percentages scale from it.
- `width: X` marks a column as the flexible `tabularx` column.
- `width: auto` on a column is also treated as a flexible `X` column.
- `width-group: quarter` makes all matching columns equal-width `X` columns
  when no explicit width is supplied.
- Raw strings such as `2.5cm` are passed through as LaTeX lengths.

You can force long-table rendering:

```yaml
table:
  long: true
```

`long: auto` is the default. `placement` accepts LaTeX float placement
letters such as `htbp`:

```yaml
table:
  placement: htbp
```

## Markdown Inside Cells

Inline Markdown survives inside cells:

```yaml
columns: [Requirement, Notes]
rows:
  - [REQ-001, "**Must** support `CSV` import"]
  - [REQ-002, "See [the spec](./spec.md) before shipping"]
```

Keep the values quoted when Markdown punctuation would otherwise confuse YAML.

## Plain Markdown Tables with `yaml table-config`

For small tables, pipe syntax is still the fastest input. Add a
`yaml table-config` fence immediately after the table to route it through the
same LaTeX table renderer:

````markdown
Table: Inventaire des cours d'informatique. {#tbl:cours}

| Abbr.      | Sem. | Nom du cours                          | Orientations | Charge |
| ---------- | ---- | ------------------------------------- | ------------ | ------ |
| Info1      | S1   | Informatique 1                        | E,M,A,N      | 120    |
| MicroInfo  | S1   | Microcontrôleurs et microinformatique | E,M,A,N      | 120    |
| Info2      | S2   | Informatique 2                        | E,M,A,N      | 100    |

```yaml table-config
columns:
  - {align: left}
  - {align: right}
  - {align: justify, width: X}
  - {align: left}
  - {align: right}
```
````

`columns` is matched positionally against the Markdown table columns. The
example above produces a `lrXlr` column spec: the course-name column wraps and
absorbs the remaining line width, while the other columns keep natural width.

`yaml table-config` accepts:

```yaml
table:
  width: 100%
  placement: htbp
  long: auto
columns:
  - {align: left}
  - {align: right, width: X}
  - {align: center, width-group: metrics}
```

It does not add grouped headers, spans, separators, or footers to a Markdown
table. Use full `yaml table` when the structure itself is complex.

## Complete Examples

### Grouped Financial Header

````markdown
Table: Quarterly sales by product (2023-2024)

```yaml table
table:
  width: 100%
columns:
  - Product
  - name: FY23
    columns: [Q1, Q2, Q3, Q4]
    width-group: quarter
  - name: FY24
    columns: [Q1, Q2, Q3, Q4]
    width-group: quarter
rows:
  - [Apples,   [120, 135, 150, 140], [130, 145, 160, 150]]
  - [Pears,    [80,  90,  110, 85],  [85,  95,  115, 90]]
  - [Peaches,  [60,  95,  110, 40],  [55,  100, 120, 45]]
  - separator: true
  - [Cherries, [~,   ~,   45,  0],   [~,   ~,   50,  0]]
  - [Plums,    [0,   0,   30,  75],  [0,   0,   35,  80]]
footer:
  - [Total, [260, 320, 445, 340], [270, 340, 480, 365]]
```
````

### Three-Level Header

````markdown
Table: Monthly sales breakdown for 2024

```yaml table
columns:
  - Product
  - name: 2024
    columns:
      - name: Q1
        columns: [Jan, Feb, Mar]
      - name: Q2
        columns: [Apr, May, Jun]
rows:
  - [Alpha, [10, 12, 15, 18, 20, 22]]
  - [Beta,  [~,  ~,  5,  8,  10, 12]]
```
````

### Fixed Columns plus Flexible Text

````markdown
Table: Product requirements (fixed + flexible columns)

```yaml table
table:
  width: 90%
columns:
  - name: Requirement
    width: 25%
    align: l
  - name: Description
    align: j
  - name: Priority
    width: 15%
    align: c
rows:
  - [REQ-001, "The system must support CSV import with automatic delimiter detection.", High]
  - [REQ-002, "PDF exports must follow the brand guidelines (logo, colours, margins).", Medium]
  - [REQ-003, "The UI must be fully keyboard accessible (WCAG 2.1 AA).", High]
```
````

## Validation Errors

The YAML table parser validates the table before the LaTeX renderer sees it.
When something is wrong, TeXSmith emits an inline error block and keeps the
document buildable.

Common failures:

- Unknown top-level keys.
- Missing `columns`.
- Rows with too many or too few cells.
- Unknown column names in named-row mode.
- Span rectangles whose absorbed slots are not `~`.
- Invalid alignment values.
- Invalid percentage widths.

Example:

````markdown
```yaml table
columns:
  - Year
  - name: Actual
    columns: [H1, H2]
rows:
  - 2024: {Acutal: [6, 7]}
```
````

The typo `Acutal` is reported with the available column names. That is the
point of making complex tables data-shaped instead of pretending that pipe
tables are a database.
