---
press:
  columns: 2
---
# Emoji Support

## Introduction

TeXSmith renders emoji as glyphs when you pick a font flavour:

```yaml
press:
  fonts:
    emoji: black
```

You can choose among four built-in options:

`black`
: OpenMoji Black (default).

`color`
: Noto Color Emoji.

`twemoji`
: Use the `twemoji` package as fallback.

`artifact`
: Download emoji as images using Twemoji.

Any other name is treated as a custom font family to load directly.

Engines:

- LuaLaTeX relies on `luaotfload` to add the emoji font as a fallback.
- XeLaTeX/Tectonic use `ucharclasses` to automatically switch to the emoji font on the U+1F000–U+1FAFF range.
You can type emoji directly in Markdown or LaTeX source.

/// latex
\newpage
///

## Examples

| Emoji | Description                    |
| ----- | ------------------------------ |
| 😊    | Smiling face with smiling eyes |
| 🚀    | Rocket                         |
| 🍕    | Pizza                          |
| 🎉    | Party popper                   |
| 🐍    | Snake                          |
| 🌍    | Globe showing Europe-Africa    |
| 💻    | Laptop computer                |
| 📚    | Books                          |
| 🎨    | Artist palette                 |
| 👽    | Alien                          |
| 👋    | Waving hand                    |
| 🤖    | Robot                          |
| 🦄    | Unicorn                        |
| 🧠    | Brain                          |
| 🛸    | Flying saucer                  |
| 🛰️    | Satellite                      |
| 🐙    | Octopus                        |
| 📝    | Memo                           |
| 📋    | Note                           |
| ⭐    | Star                           |
| ✅    | Check mark                     |
| ❌    | Cross mark                     |
| 🧪    | Experiment                     |
| 💡    | Light Bulb                     |
