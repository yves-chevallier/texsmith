#set page(margin: 2.5cm)
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true)

= Advanced Tables Formatting

One true missing feature in Markdown and in most LaTeX documents is the
ability to describe complex tables without tedious boilerplate. The standard
Markdown specification is too restrictive — no multi-line cells, no multi-row
or multi-column cells, no meta-information — and raw LaTeX tables require too
much scaffolding. TeXSmith keeps Markdown for simple tables and introduces a
YAML-based description for the complex ones.

The supported features are:

- Multi-line cells
- Multi-row and multi-column cells, both in headers and in the body
- Horizontal separators, with optional section label
- Footer rows (summary rows)
- Column alignment (`l`, `c`, `r`) with per-cell override
- Width groups (columns sharing the same width)
- Overall table width (`auto`, a percentage of `\linewidth`, or a fixed length)
- Markdown formatting preserved inside cells
- Captions and labels via the standard `Table: …` syntax
- Full HTML output with enough meta-information for the LaTeX renderer to
    pick the right environment (`tabular`, `tabularx`, or `longtable`)

Each section below shows the YAML source on the left and the rendered table
right after, so you can compare input and output at a glance.

== Captions and labels

A YAML table is written as a fenced code block whose info string is
`yaml table`. Captions follow the standard TeXSmith `Table: …` syntax placed
on the line directly above the fence; an optional `{#tbl:foo}` adds a
referenceable label.

Notable attributes:

- The first column is the *label column* (its values become the row
    headers); subsequent columns hold data.
- `~` (YAML null) marks an empty cell.
- A `separator:` row inserts a horizontal rule and may carry a `label:` for
    a section title.
- The `footer:` block produces summary rows separated from the body by an
    extra rule.

Source:

```yaml
columns: [Fruit, Geneva, Zurich, Basel]
rows:
  - [Apples,   120, 180, 90]
  - [Pears,    45,  ~,   110]
  - separator: {label: Seasonal shortage}
  - [Apricots, 5,   0,   12]
footer:
  - [Total, 170, 180, 212]
```

Rendered:

#figure(
  table(
    columns: 4,
    align: (left, left, left, left),
    table.header([Fruit], [Geneva], [Zurich], [Basel]),
    [Apples], [120], [180], [90],
    [Pears], [45], [], [110],
    table.hline(),
    table.cell(colspan: 4)[_Seasonal shortage_],
    [Apricots], [5], [0], [12],
    table.hline(),
    [Total], [170], [180], [212],
  ),
  caption: [Fruit stock by warehouse],
)

The table above can be referenced with `[see @tbl:stock]` like any other
TeXSmith float.

== Complex grouped headers

A column can either be a leaf (a string or `{name, …}` mapping) or a group
(`{name, columns: [...]}`). Groups can carry their own metadata that
propagates to their leaves.

Notable attributes:

- `table.width: 100%` forces the table to span `\linewidth` and selects
    `tabularx` as the LaTeX environment.
- `width-group: <id>` makes every column carrying the same identifier share
    the same width — perfect for keeping the FY23 and FY24 quarters aligned.
- The label column (`Product`) is left auto-sized; only the columns inside
    width-groups absorb the remaining horizontal space.
- A list cell `[120, 135, 150, 140]` fills a grouped column's leaves
    positionally; `~` inside such a list leaves an empty leaf.

Source:

```yaml
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

Rendered:

#figure(
  table(
    columns: 9,
    align: (left, left, left, left, left, left, left, left, left),
    table.header(table.cell(rowspan: 2)[Product], table.cell(colspan: 4)[FY23], table.cell(colspan: 4)[FY24], [Q1], [Q2], [Q3], [Q4], [Q1], [Q2], [Q3], [Q4]),
    [Apples], [120], [135], [150], [140], [130], [145], [160], [150],
    [Pears], [80], [90], [110], [85], [85], [95], [115], [90],
    [Peaches], [60], [95], [110], [40], [55], [100], [120], [45],
    table.hline(),
    [Cherries], [], [], [45], [0], [], [], [50], [0],
    [Plums], [0], [0], [30], [75], [0], [0], [35], [80],
    table.hline(),
    [Total], [260], [320], [445], [340], [270], [340], [480], [365],
  ),
  caption: [Quarterly sales by product (2023-2024)],
)

== Named-row mode

The same data can be written declaratively, where each row explicitly names
the columns it fills. Unspecified columns are left empty and typos in column
names are caught as validation errors.

Notable attributes:

- Shorthand form `{Apples: {FY23: [...], FY24: [...]}}` — the row's only key
    is the label, mapped to a dict of column-name → value.
- Explicit form `{label: …, cells: {…}}` lets you spell things out and
    document each row.
- Listing only some columns is fine; the others render as empty cells.

Source:

```yaml
columns:
  - Product
  - name: FY23
    columns: [Q1, Q2, Q3, Q4]
  - name: FY24
    columns: [Q1, Q2, Q3, Q4]
rows:
  - Apples:  {FY23: [120, 135, 150, 140], FY24: [130, 145, 160, 150]}
  - Pears:   {FY23: [80,  90,  110, 85],  FY24: [85,  95,  115, 90]}
  - Peaches: {FY23: [60,  95,  110, 40],  FY24: [55,  100, 120, 45]}
  - separator: true
  - label: Cherries
    cells: {FY23: [~, ~, 45, 0]}   # FY24 omitted = empty
```

Rendered:

#figure(
  table(
    columns: 9,
    align: (left, left, left, left, left, left, left, left, left),
    table.header(table.cell(rowspan: 2)[Product], table.cell(colspan: 4)[FY23], table.cell(colspan: 4)[FY24], [Q1], [Q2], [Q3], [Q4], [Q1], [Q2], [Q3], [Q4]),
    [Apples], [120], [135], [150], [140], [130], [145], [160], [150],
    [Pears], [80], [90], [110], [85], [85], [95], [115], [90],
    [Peaches], [60], [95], [110], [40], [55], [100], [120], [45],
    table.hline(),
    [Cherries], [], [], [45], [0], [], [], [], [],
  ),
  caption: [Same sales, named-row mode],
)

== Three-level headers

Headers can nest arbitrarily deeply. The example below shows a
year → quarter → month hierarchy that produces three header rows with
`\cmidrule` strokes between groupings.

Notable attributes:

- Each `name + columns` block adds one extra header level.
- A single list cell `[10, 12, 15, 18, 20, 22]` flattens across all leaves of
    the outer group regardless of nesting depth.

Source:

```yaml
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

Rendered:

#figure(
  table(
    columns: 7,
    align: (left, left, left, left, left, left, left),
    table.header(table.cell(rowspan: 3)[Product], table.cell(colspan: 6)[2024], table.cell(colspan: 3)[Q1], table.cell(colspan: 3)[Q2], [Jan], [Feb], [Mar], [Apr], [May], [Jun]),
    [Alpha], [10], [12], [15], [18], [20], [22],
    [Beta], [], [], [5], [8], [10], [12],
  ),
  caption: [Monthly sales breakdown for 2024],
)

== Multi-row cell in the body

Any cell can be promoted to a _rich cell_ (a mapping with `value`, `rows`,
`cols` and/or `align`). Setting `rows: N` makes the cell span `N` consecutive
rows; the next `N-1` rows must use `~` at the same column position to
acknowledge the absorption — the validator refuses anything else.

Notable attributes:

- `{value: Maria, rows: 2}` — span two rows, value rendered via LaTeX
    `\multirow`.
- The absorbing `~` is required (the validator rejects a stray real value
    there with a clear error).

Source:

```yaml
columns: [Article, Editor, Status, Pages]
rows:
  - [Alpha, {value: Maria, rows: 2}, Draft,     12]
  - [Beta,  ~,                        Review,    18]
  - [Gamma, John,                     Published, 24]
```

Rendered:

#figure(
  table(
    columns: 4,
    align: (left, left, left, left),
    table.header([Article], [Editor], [Status], [Pages]),
    [Alpha], table.cell(rowspan: 2)[Maria], [Draft], [12],
    [Beta], [Review], [18],
    [Gamma], [John], [Published], [24],
  ),
  caption: [Article assignments (same editor spans two rows)],
)

== Multi-column cell in the body

`cols: N` makes a cell span `N` consecutive leaf columns. It's most useful
under a grouped header to fold a totals row across all sub-columns at once.

Notable attributes:

- `cols: 4` consumes the four leaves of the `2024` group in one cell.
- `align: c` overrides the column's default alignment for this cell only
    (rendered via LaTeX `\multicolumn{N}{c}{…}`).

Source:

```yaml
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

Rendered:

#figure(
  table(
    columns: 5,
    align: (left, left, left, left, left),
    table.header(table.cell(rowspan: 2)[Metric], table.cell(colspan: 4)[2024], [Q1], [Q2], [Q3], [Q4]),
    [Revenue], [120], [130], [150], [170],
    [Cost], [80], [85], [90], [95],
    table.hline(),
    [Gross], table.cell(colspan: 4, align: center)[\$570k],
  ),
  caption: [Annual totals across all four quarters],
)

== Mixed block (rowspan × colspan)

A cell can combine `rows` and `cols` to span a rectangle. The absorbed cells
form a `rows × cols` block and must all be filled with `~`.

Notable attributes:

- `{value: "Merged 2x3", rows: 2, cols: 3, align: c}` — a single declaration
    drives both the LaTeX `\multirow` and `\multicolumn` emission.
- The absorbed row needs `~` for each of the three absorbed columns.

Source:

```yaml
columns: [A, B, C, D]
rows:
  - [r1, {value: "Merged 2x3", rows: 2, cols: 3, align: c}]
  - [r2, ~,                                                 ~, ~]
  - [r3, x, y, z]
```

Rendered:

#figure(
  table(
    columns: 4,
    align: (left, left, left, left),
    table.header([A], [B], [C], [D]),
    [r1], table.cell(colspan: 3, rowspan: 2, align: center)[Merged 2x3],
    [r2],
    [r3], [x], [y], [z],
  ),
  caption: [2×3 merged block highlight],
)

== Width control

By default the table width is `auto` (natural column widths, `tabular`).
Setting `table.width` to a percentage of `\linewidth` forces the table to
span that width and selects `tabularx`, with at least one column kept
flexible (`X`) to absorb the remainder. Individual columns can carry a fixed
`width` (an absolute length or a percentage of the table); columns sharing
the same `width-group` are forced to match.

=== Fixed columns + flexible description

Notable attributes:

- `align: j` (justified) is applied to the `Description` column, which is
    the only one without an explicit width — it becomes the flexible `X`
    column that absorbs the remainder.
- `align: l` and `align: c` set left and centre alignment on the fixed
    columns.

Source:

```yaml
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

Rendered:

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header([Requirement], [Description], [Priority]),
    [REQ-001], [The system must support CSV import with automatic delimiter detection.], [High],
    [REQ-002], [PDF exports must follow the brand guidelines (logo, colours, margins).], [Medium],
    [REQ-003], [The UI must be fully keyboard accessible (WCAG 2.1 AA).], [High],
  ),
  caption: [Product requirements (fixed + flexible columns)],
)

=== Equal-width columns via width-group

Notable attributes:

- All four quarter columns share `width-group: quarter`, so `tabularx`
    divides the available width equally between them.
- `Category` has no width and no group — it stays auto-sized.

Source:

```yaml
table:
  width: 100%
columns:
  - Category
  - name: Q1
    width-group: quarter
  - name: Q2
    width-group: quarter
  - name: Q3
    width-group: quarter
  - name: Q4
    width-group: quarter
rows:
  - [Salaries,    120000, 122000, 121000, 125000]
  - [Equipment,   15000,  8000,   22000,  11000]
  - [Contractors, 30000,  32000,  28000,  35000]
footer:
  - [Total, 165000, 162000, 171000, 171000]
```

Rendered:

#figure(
  table(
    columns: 5,
    align: (left, left, left, left, left),
    table.header([Category], [Q1], [Q2], [Q3], [Q4]),
    [Salaries], [120000], [122000], [121000], [125000],
    [Equipment], [15000], [8000], [22000], [11000],
    [Contractors], [30000], [32000], [28000], [35000],
    table.hline(),
    [Total], [165000], [162000], [171000], [171000],
  ),
  caption: [Quarterly budget (equal-width columns via width-group)],
)

== Headerless tables

Sometimes a table is just a two-column key/value summary — no real column
headers, only the rows themselves. Omit the `name` field on every column and
the renderer drops the `<thead>` (and the corresponding LaTeX `\midrule`)
so the body sits directly under the `\toprule`. The columns still accept
`align`, `width`, and `width-group` exactly as in a regular table.

Notable attributes:

- No `name:` on any column → no header rows emitted.
- The first column remains the *label column*; row labels still take the
    first cell of each row.
- Per-column `align` and `width` keep their usual meaning, so a typical
    headerless layout is a fixed-width key column plus a justified value
    column that absorbs the remainder of the line.

Source:

```yaml
table:
  width: 100%
columns:
  - align: l
    width: 40%
  - align: j
rows:
  - ["Project codename", "Northwind"]
  - ["Workload estimate", "25 × 7 = 175 hours"]
  - ["Supervised sessions", "7 × 16 = 112 periods"]
  - ["Independent study", "175 − 112 = 63 hours"]
  - ["Theory / practice mix", "50 % theory, 50 % lab"]
```

Rendered:

#table(
  columns: 2,
  align: (left, left),
  [Project codename], [Northwind],
  [Workload estimate], [25 × 7 = 175 hours],
  [Supervised sessions], [7 × 16 = 112 periods],
  [Independent study], [175 − 112 = 63 hours],
  [Theory / practice mix], [50 % theory, 50 % lab],
)

== Plain Markdown tables, qualified by `yaml table-config`

Markdown's pipe table syntax stays the most ergonomic input format for short,
literal tables. To give those tables real LaTeX semantics — picking
`tabularx`, choosing alignment per column, marking one column as the
flexible (`X`) one — drop a `yaml table-config` fence right below the
markdown table:

Notable attributes:

- The fence is a regular code block whose info string is `yaml table-config`.
    It must directly follow the table (only the standard blank line in
    between).
- `columns` is matched *positionally* to the markdown columns; no `name`
    is required.
- `align` accepts both short forms (`l`, `c`, `r`, `j`) and long forms
    (`left`, `center`, `right`, `justify`).
- `width: X` (case-insensitive) marks a column as the flexible one — it
    becomes the LaTeX `X` column that absorbs the remaining width. Other
    columns size to their content. The renderer automatically switches the
    table to `tabularx{\linewidth}{…}`.
- Standard `width` values (percentages, lengths) and `width-group` work
    the same as in full yaml-tables.

Source:

```markdown
Table: Inventaire des cours d'informatique. {#tbl:cours}

| Abbr.      | Sem. | Nom du cours                          | Orientations | Charge |
| ---------- | ---- | ------------------------------------- | ------------ | ------ |
| Info1      | S1   | Informatique 1                        | E,M,A,N      | 120    |
| MicroInfo  | S1   | Microcontrôleurs et microinformatique | E,M,A,N      | 120    |
| Info2      | S2   | Informatique 2                        | E,M,A,N      | 100    |

texsmith-table-config-marker-0
```

Rendered:

#figure(
  table(
    columns: 5,
    align: (left, left, left, left, left),
    table.header([Abbr.], [Sem.], [Nom du cours], [Orientations], [Charge]),
    [Info1], [S1], [Informatique 1], [E,M,A,N], [120],
    [MicroInfo], [S1], [Microcontrôleurs et microinformatique], [E,M,A,N], [120],
    [Info2], [S2], [Informatique 2], [E,M,A,N], [100],
  ),
  caption: [Inventaire des cours d'informatique.],
)

The colspec produced is `lrXlr`: `Nom du cours` is the only column to wrap
its contents and absorb the remainder of `\linewidth`; the other four size
to their natural width.

== Error cases

Validation errors surface as inline error admonitions: the document still
builds, but a clearly identified block tells you exactly what went wrong and
where. Each error case below is a deliberate mistake.

=== Wrong cell count

A row with too few or too many cells is rejected.

```yaml
columns: [A, B, C, D]
rows:
  - [x, 1, 2]   # missing a cell
```

Rendered:

#block(stroke: 0.5pt, inset: 8pt, radius: 2pt, width: 100%)[
  [*YAML table error*]
  ```
  body row 'x' covers 2 leaf cell(s); expected 3
  ```
]

=== Unknown column in named-row mode

A typo in a named-row column key surfaces with a list of the available
column names.

```yaml
columns:
  - Year
  - name: Actual
    columns: [H1, H2]
rows:
  - 2024: {Acutal: [6, 7]}   # typo: "Acutal" instead of "Actual"
```

Rendered:

#block(stroke: 0.5pt, inset: 8pt, radius: 2pt, width: 100%)[
  [*YAML table error*]
  ```
  named row 2024: unknown column(s) ['Acutal']; available columns: ['Actual']
  ```
]

=== Multirow / multicolumn rectangle not absorbed

When a rich cell declares a rectangle, the absorbed positions on subsequent
rows must be `~`. Forgetting them is caught by the validator.

```yaml
columns: [A, B, C, D]
rows:
  - [r1, {value: "Block", rows: 2, cols: 2}]
  - [r2, a, b, c]   # missing the ~ cells that absorb the 2×2 block
```

Rendered:

#block(stroke: 0.5pt, inset: 8pt, radius: 2pt, width: 100%)[
  [*YAML table error*]
  ```
  body row 'r1' covers 2 leaf cell(s); expected 3
  ```
]
