# Geometry Fragment

The geometry fragment allows you to customize the page layout of your document, including paper size, orientation, margins, and adding watermarks. It relies on the LaTeX `geometry` package to manage these settings and uses TikZ for watermarking if you want any.

## Paper format

We support standard paper formats recognized by the LaTeX `geometry` package. You can specify the format using the `paper.format` key. For example, to set the paper size to A5, you would use:

```yaml
press:
  paper: a5
```

The supported formats include but are not limited to: a0, a1, a2, a3, a4, a5, a6, b0, b1, b2, b3, b4, b5, b6, c0, c1, c2, c3, c4, c5, c6, letter, legal, executive, ansia, ansib, ansic, ansid, ansie.

!!! note

    The default format is `a4`, in contrast to LaTeX’s `letter` default.
    Globally, only the United States, Canada, Mexico, and a few Caribbean
    countries primarily use the `letter` size -- roughly 500 million people. The
    rest of the world, representing more than 6 billion people, relies on `a4`
    as the standard paper size. Given this overwhelming majority, TeXSmith
    defaults to `a4` to better serve its global user base. Sorry, folks in the
    US, Canada, and Mexico -- TeXSmith is opinionated and has chosen the
    broadest consensus!

## Orientation

You can set the page orientation using the `paper.orientation` key. The possible values are `portrait` and `landscape`. For example, to set the orientation to landscape, you would use:

```yaml
press:
  paper:
    orientation: landscape
```

## Margins

You can customize the page margins using the `paper.margin` key. You can either specify a single value for all margins or provide an object with specific margins. For example:

```yaml
press:
  paper:
    margin: 2cm
```

Or for specific margins:

```yaml
press:
  paper:
    margin:
      left: 3cm
      right: 2cm
      top: 4cm
      bottom: 5cm
```

Or use predefined margin settings like `narrow`, `moderate`, or `wide`:

```yaml
press:
  paper:
    margin: narrow
```

## Examples

Here is an example configuration that sets the paper size to C5, uses landscape orientation, adds a frame, customizes the margins, and includes a watermark:

```md
---
press:
  paper:
    format: c5
    orientation: landscape
    frame: true
    margin:
      left: 3cm
      bottom: 5
    watermark: "ENVELOPE"
---
# Custom Geometry Example

This document demonstrates custom page geometry settings using the geometry fragment.
```

```md {.snippet}
---
template: article
press:
  paper:
    format: c5
    orientation: landscape
    frame: true
    margin:
      left: 3cm
      bottom: 5
    watermark: "ENVELOPE"
---
# Custom Geometry Example

This document demonstrates custom page geometry settings using the geometry fragment.
```

Here another example with custom paper width:

```md
---
press:
  paper:
    width: 12cm
    height: 5cm
    frame: true
    margin: narrow
---
$$ E=mc^2 $$
```

```md {.snippet}
---
template: article
press:
  paper:
    width: 12cm
    height: 5cm
    frame: true
    margin: narrow
---
$$ E=mc^2 $$
```
