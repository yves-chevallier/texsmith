# Test Snippet

## Bibliography caption

```md {.snippet caption="Demo" width="70%"}
---
suppress_title_metadata: true
press:
  template: article
  paper:
    width: 170mm
    height: 90mm
    orientation: landscape
bibliography:
  WADHWANI20111713: https://doi.org/10.3168/jds.2010-3952
fragments:
  ts-frame:
frame: true
---
# Citation Demo

Cheese exhibits unique melting properties [^WADHWANI20111713].
```

## Watermark

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
fragments:
  ts-frame:
frame: true
---
# Custom Geometry Example

This document demonstrates custom page geometry settings using the geometry fragment.
```

## Admonitions

```yaml {.snippet caption="Demo" width="70%"}
cwd: examples/admonition
sources:
  - admonition.md
press:
  callout_style: fancy
fragments:
  ts-frame:
frame: true
```
