# Bibliography

## Add Bibliography Entries

To include bibliography entries in your document, provide one or more BibTeX files as inputs when running TeXSmith. TeXSmith will parse these files and integrate the references into your document during the conversion process. For example:

```bash
texsmith paper.md nature.bib ieee.bib -o paper.pdf
```

## List Bibliography Entries

Use the `--list-bibliography` flag to inspect BibTeX files before running a conversion or build. It helps catch parsing issues, duplicate entries, and empty datasets early in your workflow. For example in the `paper` example project:

```text
$ texsmith cheese.md cheese.bib --list-bibliography

                    Bibliography Files
┌──────────────────────────────────────────────┬─────────┐
│ File                                         │ Entries │
├──────────────────────────────────────────────┼─────────┤
│ /home/ycr/texsmith/examples/paper/cheese.bib │       2 │
│ Total                                        │       2 │
└──────────────────────────────────────────────┴─────────┘
                              Jaoac2019 (article)
  Title    Determination of Moisture in Cheese and Cheese Products
  Year     2019
  Journal  Journal of AOAC INTERNATIONAL
  Authors  Jr Bradley Robert L, Margaret A Vanderwarn
  Sources  /home/ycr/texsmith/examples/paper/cheese.bib
  Abstract Variables related to oven-drying samples of cheese and cheese
           products to determine moisture...
  Doi      10.1093/jaoac/84.2.570
  Eprint   https://academic.oup.com/jaoac/article-pdf/84/2/570/32415847/jaoac…
  Issn     1060-3271
  Month    11
  Number   2
  Pages    570-592
  Url      https://doi.org/10.1093/jaoac/84.2.570
  Volume   84


                             Prentice1993 (inbook)
  Title     Cheese Rheology
  Year      1993
  Authors   J. H. Prentice, K. R. Langley, R. J. Marshall
  Sources   /home/ycr/texsmith/examples/paper/cheese.bib
  Abstract  Rheology is formally defined as the study of the flow and
            deformation of matter...
  Address   Boston, MA
  Booktitle Cheese: Chemistry, Physics and Microbiology: Volume 1 General
            Aspects
  Doi       10.1007/978-1-4615-2650-6_8
  Isbn      978-1-4615-2650-6
  Pages     303--340
  Publisher Springer US
  Url       https://doi.org/10.1007/978-1-4615-2650-6_8


    Bibliography Summary
┌───────────────────┬───────┐
│ Category          │ Count │
├───────────────────┼───────┤
│ Total entries     │     2 │
│ From cheese.bib   │     2 │
│ From front matter │     0 │
│ From DOI fetches  │     0 │
└───────────────────┴───────┘
```

## Behaviour

TeXSmith will loads every provided `.bib` file using `pybtex` and analyses their contents, fetch for duplicate keys, and check for parsing errors. It will emit warnings for any issues found, and print a summary table of the number of entries per file.

The `--list-bibliography` flag has the following behaviour:

- Prints a formatted table summarising the number of entries per file.
- Emits warnings for files that fail to parse, contain duplicate keys, or are empty.
- Highlights issues detected by TeXSmith’s bibliography loader (e.g. conflicting entries sourced from multiple files).
- Exits before rendering anything else, so you can run it as a fast preflight step.
