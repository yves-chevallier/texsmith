# Font management

The built-in `ts-fonts` fragment now takes care of two pieces at once:

- It resolves the font profile (Latin Modern, TeX Gyre, Noto…) and copies the matching font files into `build/fonts/`.
- It inspects your document to discover any Unicode ranges that need a fallback and wires the right Noto families either through LuaLaTeX fallbacks or ucharclasses for XeLaTeX/Tectonic.

## How fonts are selected

`ts-fonts` still honours the `fonts` profile (`default`, `sans`, `adventor`, `heros`, `noto`). The selection is resolved before rendering so the template knows exactly which main, sans, mono, math, and small-caps families to load. Those families — plus the detected fallbacks — are looked up with the new `FontLocator`, copied next to the build artefacts, and referenced via `Path=./fonts/…` so engines that dislike absolute paths (notably Tectonic) stay happy.

## Unicode fallbacks

TeXSmith bundles a Noto coverage index. During rendering we collate the Unicode characters from the template context, ask the index which families are required, and then:

- On **LuaLaTeX**, we keep using `luaotfload.add_fallback`, but the chain now prefers the copied font files (`file:./fonts/...`) when available.
- On **XeLaTeX/Tectonic**, we generate `ucharclasses` on the fly: each fallback family gets a `\newfontfamily` with the copied files and a set of `\setUnicodeClassRange{...}{"XXXX->"YYYY"}` declarations that only trigger when the document actually contains those ranges.

If you provide a custom `fonts.yaml`, it is used both for coverage matching and to discover which files to copy.

## API helpers

Two helpers are exposed for custom tooling:

- `NotoFallback` wraps the coverage index and produces `FontMatchResult` instances or ucharclass-ready specs.
- `FontLocator` queries the system (via `fc-list` when available) or your `fonts.yaml` to find and copy font files.

Example:

```python
from pathlib import Path
from texsmith.fonts import FontLocator, NotoFallback

text = "مرحبا 世界"
fallback = NotoFallback()
match = fallback.match_text(text, check_system=False)

locator = FontLocator()
copied = locator.copy_families(match.fallback_fonts, Path("build/fonts"))
print(match.font_ranges)        # Unicode ranges per family
print({k: v.available() for k, v in copied.items()})
```

Use these helpers when you need to preflight a document or stage fonts ahead of running the full template pipeline.
