
# Tables

## Complex Tables

Markdown offers limited table configuration—only column alignment by default. PyMdown provides captions, and superfences can inject more metadata, but we still miss:

- Table width (auto vs. full width)
- Resizing oversized tables
- Orientation (portrait vs. landscape)
- Column and row spanning
- Horizontal and vertical separator lines
- Column widths (fixed, auto, relative)

### Extended Markdown Table Syntax

Leverage Pymdown’s table extension to add more metadata directly in Markdown. For example:
texsmith.spantable extension lets us span cells in standard Markdown tables.

The `>>>` syntax will span cells horizontally, the `vvv` syntax will span cells vertically.

```markdown
| Header 1 | Header 2 | Header 3 |
|:---------|:--------:|---------:|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | >>>      | Cell 6   |
| Cell 7   | Cell 8   | Cell 11  |
| Cell 9   |          | vvv      |
```

### Cmi rules example

```latex
\begin{tabular}{@{}lll@{}}
\toprule
& \multicolumn{2}{c}{Reaction} \\
\cmidrule(l){2-3}
Person & Face & Exclamation \\
\midrule
\multirow[t]{2}{*}{VIPs} & :) & Nice \\
& :] & Sleek \\
Others & \multicolumn{2}{c}{Not available} \\
\bottomrule
\end{tabular}
```

### Align to dot number

Find a syntax to align numbers to dot. `lS@{}`

### Raw table syntax

Superfences do not work directly with tables, so define a `table` fence that accepts YAML options:

````markdown
```table
width: full
caption: Sample Table
label: tbl:sample
header: true
print:
  orientation: landscape
  resize: true
columns:
  - alignment: left
    width: auto
  - alignment: center
    width: 2cm
  - alignment: right
    width: auto
rows:
  - height: auto
    alignment: top
    span: [2, auto]
data:
  - [Cell 1, Cell 2, Cell 3]
  - [Cell 4, null, Cell 6]
  - [Cell 7, Cell 8, null]
```
````

The goal is to convert Markdown tables into LaTeX tables with automatic line breaks so that columns wrap gracefully when a table is too wide.

## Shrink-to-fit vs Auto-expand

Long table et auto ajustement.

```latex
\documentclass{article}
\usepackage[margin=2cm]{geometry}
\usepackage{booktabs}
\usepackage[french]{babel}
\usepackage{array}

% ltablex : Le pont entre tabularx et longtable
\usepackage{ltablex}

% IMPORTANT : On NE met PAS \keepXColumns ici.
% Sans cette commande, ltablex va calculer si le tableau a besoin
% de toute la largeur ou non.

\begin{document}

\section*{Cas 1 : Table petite (Compacte)}
% Ici, comme le texte est court, le tableau ne prendra pas toute la page
% Les colonnes X vont se comporter comme des colonnes 'l'
\begin{tabularx}{\textwidth}{lXX}
    \toprule
    \textbf{ID} & \textbf{Statut} & \textbf{Note} \\
    \midrule
    \endfirsthead
    1 & OK & R.A.S. \\
    \midrule
\end{tabularx}

\vspace{2cm}

\section*{Cas 2 : Table large (Extension automatique)}
% Ici, le texte est long. Le tableau va détecter qu'il dépasse,
% s'étendre jusqu'à \textwidth, et activer le retour à la ligne.
\begin{tabularx}{\textwidth}{lXX}
    \toprule
    \textbf{ID} & \textbf{Description} & \textbf{Analyse} \\
    \midrule
    \endfirsthead

    \textbf{ID} & \textbf{Description} & \textbf{Analyse} \\
    \midrule
    \endhead

    204 &
    Ici j'ai un texte suffisamment long pour justifier que le tableau prenne toute la largeur disponible sur la page. &
    Et ici une autre colonne qui va se partager l'espace restant équitablement avec la colonne précédente. \\

    205 & Test de remplissage & Encore du texte... \\
    \bottomrule
\end{tabularx}
\end{document}
```

We could use a tester to have a rough idea if the table will fit or not, and decide to use `tabularx` or `ltablex` accordingly.

```tex
\documentclass{article}
\usepackage{booktabs}
\usepackage{tabularx} % ou tabularray (tblr), etc.

\newsavebox{\tblbox}

\begin{document}
\typeout{TEXTWIDTH_PT=\the\textwidth}
\typeout{LINEWIDTH_PT=\the\linewidth}
\typeout{COLUMNWIDTH_PT=\the\columnwidth}
\typeout{PAPERWIDTH_PT=\the\paperwidth}
\typeout{PAPERHEIGHT_PT=\the\paperheight}
\thispagestyle{empty}

\sbox{\tblbox}{%
  \begin{tabular}{l l r}
    \toprule
    Item & Description & Price\\
    \midrule
    Pink Rabbit & A small pink puppet made of soft fur. & \$10\\
    \bottomrule
  \end{tabular}%
}

\typeout{TABLE_WD_PT=\the\wd\tblbox}
\typeout{TABLE_HT_PT=\the\dimexpr\ht\tblbox+\dp\tblbox\relax}

\end{document}
```
