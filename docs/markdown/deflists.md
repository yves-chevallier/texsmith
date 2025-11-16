# Definition Lists

Definition Lists allow you to create lists of terms and their corresponding definitions. The syntax for creating a definition list is as follows:

```markdown
Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.
```

Rendered as:

Apple
:   Pomaceous fruit of plants of the genus Malus in
    the family Rosaceae.

Orange
:   The fruit of an evergreen tree of the genus Citrus.

The LaTeX corresponding output is:

```latex
\begin{description}
\item[Apple] Pomaceous fruit of plants of the genus Malus in the family Rosaceae.
\item[Orange] The fruit of an evergreen tree of the genus Citrus.
\end{description}
```