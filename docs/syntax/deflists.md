# Definition Lists

Definition lists pair a term with one or more definitions. Markdown sticks to a simple pattern:

```markdown
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```

Which renders as:

Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.

LaTeX output:

```latex
\begin{description}
\item[Apple] Pomaceous fruit of plants of the genus Malus in the family Rosaceae.
\item[Orange] The fruit of an evergreen tree of the genus Citrus.
\end{description}
```

```md { .snippet }
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```
