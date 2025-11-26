# TeX Engines

TeX has grown far beyond Knuth’s original engine, evolving into a whole ecosystem of specialized typesetting machines. Each engine inherits the soul of classic TeX but adds its own twist—some focusing on programmability, others on Unicode, scripting, or a modern toolchain experience. Together they form a strange but delightful family tree where 1980s design meets cutting-edge typography.

## TeX

The original TeX engine, created by Donald Knuth, is the minimalist mathematical core of the entire ecosystem. It’s deterministic, stable to the point of obsession, and designed so its output will match *forever*. It handles typesetting with surgical precision but offers no frills—no Unicode, no PDF output, and no modern scripting hooks. Pure, legendary, and a little bit stubborn.

## E-TeX

e-TeX extends TeX with much-needed programming features without altering the underlying output. It adds new registers, improved conditionals, and tracing tools, making it a favorite for macro designers and format creators (like LaTeX). Think of it as TeX with a Swiss-army-knife upgrade.

## pdfTeX

pdfTeX brought TeX into the era of digital documents by producing PDF natively instead of going through DVI. It introduced microtypography—character protrusion, font expansion, and other subtle magic that makes text look professionally polished. Most modern LaTeX distributions still rely heavily on pdfTeX.

## XeTeX

XeTeX is the engine that finally made TeX feel Unicode-native. It uses system fonts directly (TrueType, OpenType), supports complex scripts naturally, and works beautifully for multilingual documents. If you need Arabic, Chinese, Hindi, or emoji without pain, XeTeX is your friend.

## LuaTeX

LuaTeX embeds a full Lua interpreter into the engine, effectively giving TeX a programmable runtime. This allows deep customization, dynamic content generation, and powerful extensions like `luaotfload` and `luametalatex`. It’s the most flexible and hackable TeX engine, almost a TeX/Lua hybrid organism.

## Tectonic

Tectonic is a modern, Rust-powered TeX engine aiming for reproducibility and user-friendliness. It automatically fetches missing packages, builds in a sandboxed environment, and removes the traditional “TeX installation anxiety.” It tries to make TeX behave like a modern build tool with zero configuration.

## Omega (Ω) / Aleph (ℵ)

Omega (and its successor Aleph) were early attempts at adding Unicode and advanced multilingual typesetting. They never became mainstream, but their ideas paved the way for XeTeX and LuaTeX.

## pTeX / upTeX

Specialized engines designed for Japanese typesetting. pTeX handles vertical writing and Japanese line-breaking rules, while upTeX brings Unicode support to that world. They’re essential in the Japanese TeX community.

## Which to prefer?

That a debate as old as TeX itself still rages on is a testament to its complexity and versatility. For most users, **pdfTeX** or **LuaTeX** (with LaTeX macros) will cover nearly all needs. Some facts:

1. Tectonic is so smooth, it downloads packages automatically, making it great for newcomers. No need to install a heavy TeX distribution.
2. LuaLaTeX is the only engine that supports both protrusion and font expansion (microtypography) along with Lua scripting which gives a smoother pdf output.
3. XeLaTeX has similar results that Tectonic but allows `--shell-escape` for minted code highlighting.
