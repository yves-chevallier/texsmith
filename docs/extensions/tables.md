# Tables

|       Column 1       |   Col 2 | Big row span   |
| :------------------: | ------: | -------------- |
| r1_c1 spans two cols | {rspan} | One large cell |
| r2_c1 spans two rows |   r2_c2 |                |
|       {cspan}        |   r3_c2 |                |
|                      |   r4_c2 | {cspan}        |

Printed document is much more complex when it comes to tables. Markdown has a very simple syntax for tables, but it does not support all features like row spans and column spans. This extension extends the basic syntax to support these features.

- Row spans
- Column spans
- Wrap cell content if too wide
- Full width tables with variable width columns
- Caption and label
- Alignment of cell content

## Meta data approach

You can define table properties in an additional meta data block before the table:

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

We can define table with a code block using `table` as the language:

````markdown
```yml { .table }
width: 100%
span:
alignemnt:
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