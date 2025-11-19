# Tables

|       Column 1       |   Col 2 | Big row span   |
| :------------------: | ------: | -------------- |
| r1_c1 spans two cols | {rspan} | One large cell |
| r2_c1 spans two rows |   r2_c2 |                |
|       {cspan}        |   r3_c2 |                |
|                      |   r4_c2 | {cspan}        |

LaTeX tables get fancy fast: row/column spans, width constraints, captions, labels, alignment tweaks. Stock Markdown only handles the basics, so TeXSmith extends the syntax to cover:

- Row and column spans (`{rspan}`, `{cspan}`)
- Automatic cell wrapping
- Full-width tables with custom column widths
- Captions + labels for cross-references
- Per-column alignment

## Metadata approach

Attach a metadata block immediately before the Markdown table to describe layout hints:

````markdown
```yml { .meta-table }
width: 100%
align: center
columns:
  - align: center
  - align: right
  - align: left
```
````

## Code block definition

Alternatively, describe the table entirely through a fenced code block marked with `.table`:

````markdown
```yml { .table }
width: 100%
span:
alignment:
  - center
  - right
  - left
table:
  - [ "Column 1", "Col 2", "Big row span" ]
  - [ {rspan}, "r1_c1 spans two cols", "One large cell" ]
  - [ "r2_c1 spans two rows", "r2_c2", "" ]
  - [ {cspan}, "", "" ]
  - [ "", "r4_c2", {cspan} ]
```
````
