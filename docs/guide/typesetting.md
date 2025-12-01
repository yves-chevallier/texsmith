# Typesetting controls

TeXSmith bundles a `ts-typesetting` fragment that tweaks basic paragraph layout, line spacing, and optional line numbers. By default it stays silent—nothing is injected unless you set one of its options.

## Configuration

All keys live under `press.typesetting` (short aliases also work: `press.paragraph`, `paragraph`, etc.).

```yaml
press:
  typesetting:
    paragraph:
      indent: auto    # true | false | auto
      spacing: 1cm    # any TeX length; omit to keep the template default
    leading: onehalf  # single | onehalf | double | <length> | <number factor>
    lineno: true      # turn on margin line numbers
```

- `paragraph.indent` controls `\parindent` plus the memoir/article `\@afterindent…` switches. `auto` leaves the first paragraph flush and indents the following ones; `true` always indents; `false` disables indentation.
- `paragraph.spacing` sets `\parskip` to your length (leave empty for the template’s original value).
- `leading` sets line spacing. `single`, `onehalf`, and `double` call the usual spacing commands. A numeric value applies a stretch factor (`1.2` → 1.2×). A length sets `\baselineskip` directly (`1em`, `14pt`, etc.).
- `lineno: true` loads the `lineno` package and enables `\linenumbers` for the whole document.

### Class-aware spacing

- On `memoir`, the fragment uses the class-provided `\SingleSpacing`, `\OnehalfSpacing`, and `\DoubleSpacing` when available, falling back to `\baselinestretch` updates.
- On other classes (article, report…), it loads `setspace` and uses `\singlespacing`, `\onehalfspacing`, or `\doublespacing`.

### Templates

The built-in `article` and `book` templates inject `ts-typesetting` directly (no `\usepackage` file to manage). If you don’t set any of the options above, the fragment emits nothing and the templates’ stock spacing stays unchanged.***
