# TeXSmith Snippet Template

The built-in `snippet` template renders Markdown fragments inside a decorated
`tikzpicture`, perfect for standalone notes, stickers, or screenshot-friendly
callouts. It reuses TeXSmith’s article preamble (fonts, callouts, keystrokes,
progress bars) so Markdown extensions behave the same way, but swaps the
document class for `standalone` and constrains the body to a configurable
minipage.

```bash
texsmith snippet.md --template snippet \
  --attribute width=11cm \
  --attribute margin=7mm \
  --attribute dogear=12mm \
  --attribute dogear_enabled=false
```

Override attributes via front matter or CLI `--attribute` flags to tweak the
inner width, padding, dog-ear size, or border visibility. Because the template
includes the shared callout definitions, admonitions look identical to the
`article` template inside the snippet frame.
