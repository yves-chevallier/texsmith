# Box drawing

A listing that draws a tree, a table and a progress bar with the Unicode *Box
Drawing* and *Block Elements* blocks, and one Greek letter in a code fence. No
text font carries those characters: the document takes them from the Noto
fallback the `scripts` pass computes, which names a *monospace* face for the
two drawing blocks — a proportional one, which is what Unicode coverage picks
first for U+2500, is full-width and would put a tree's stems out of line with
the column above them.

It is the parity entry `box-drawing`, and one of the documents
`scripts/parity.py pdf` builds and compares: a font fallback a `.tex` baseline
records is a `\newfontfamily` line until something typesets it.
