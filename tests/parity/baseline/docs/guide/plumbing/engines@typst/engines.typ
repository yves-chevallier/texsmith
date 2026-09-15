#set document(
title: "TeX Engines",
)
#set page(
paper: "a4",
margin: 2.5cm,
numbering: none,
footer: context {
if counter(page).final().first() > 1 {
align(center)[#counter(page).get().first()]
}
},
)
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#set par(justify: true)
#show heading: set block(above: 1.8em, below: 1.0em)
#set heading(numbering: "1.1")

#align(center)[
#text(size: 1.8em, weight: "bold")[TeX Engines]]
#v(1.5em)

#ts-callout-style.update("fancy")

#ts-logo("TeX") has grown far beyond Knuth’s original engine, evolving into a whole ecosystem of specialized typesetting machines. Each engine inherits the soul of classic #ts-logo("TeX") but adds its own twist—some focusing on programmability, others on Unicode, scripting, or a modern toolchain experience. Together they form a strange but delightful family tree where 1980s design meets cutting-edge typography.

= #ts-logo("TeX")

The original #ts-logo("TeX") engine, created by Donald Knuth, is the minimalist mathematical core of the entire ecosystem. It’s deterministic, stable to the point of obsession, and designed so its output will match _forever_. It handles typesetting with surgical precision but offers no frills—no Unicode, no PDF output, and no modern scripting hooks. Pure, legendary, and a little bit stubborn.

= E-#ts-logo("TeX")

e-#ts-logo("TeX") extends #ts-logo("TeX") with much-needed programming features without altering the underlying output. It adds new registers, improved conditionals, and tracing tools, making it a favorite for macro designers and format creators (like #ts-logo("LaTeX")). Think of it as #ts-logo("TeX") with a Swiss-army-knife upgrade.

= #ts-logo("pdfTeX")

#ts-logo("pdfTeX") brought #ts-logo("TeX") into the era of digital documents by producing PDF natively instead of going through DVI. It introduced microtypography—character protrusion, font expansion, and other subtle magic that makes text look professionally polished. Most modern #ts-logo("LaTeX") distributions still rely heavily on #ts-logo("pdfTeX").

= #ts-logo("XeTeX")

#ts-logo("XeTeX") is the engine that finally made #ts-logo("TeX") feel Unicode-native. It uses system fonts directly (TrueType, OpenType), supports complex scripts naturally, and works beautifully for multilingual documents. If you need Arabic, Chinese, Hindi, or emoji without pain, #ts-logo("XeTeX") is your friend.

= #ts-logo("LuaTeX")

#ts-logo("LuaTeX") embeds a full Lua interpreter into the engine, effectively giving #ts-logo("TeX") a programmable runtime. This allows deep customization, dynamic content generation, and powerful extensions like `luaotfload` and `luametalatex`. It’s the most flexible and hackable #ts-logo("TeX") engine, almost a #ts-logo("TeX")/Lua hybrid organism.

= Tectonic

Tectonic is a modern, Rust-powered #ts-logo("TeX") engine aiming for reproducibility and user-friendliness. It automatically fetches missing packages, builds in a sandboxed environment, and removes the traditional “#ts-logo("TeX") installation anxiety.” It tries to make #ts-logo("TeX") behave like a modern build tool with zero configuration.

= Omega (#mi(`\Omega`)) / Aleph (#mi(`\aleph`))

Omega (and its successor Aleph) were early attempts at adding Unicode and advanced multilingual typesetting. They never became mainstream, but their ideas paved the way for #ts-logo("XeTeX") and #ts-logo("LuaTeX").

= pTeX / upTeX

Specialized engines designed for Japanese typesetting. pTeX handles vertical writing and Japanese line-breaking rules, while upTeX brings Unicode support to that world. They’re essential in the Japanese #ts-logo("TeX") community.

= Which to prefer?

That a debate as old as #ts-logo("TeX") itself still rages on is a testament to its complexity and versatility. For most users, *#ts-logo("pdfTeX")* or *#ts-logo("LuaTeX")* (with #ts-logo("LaTeX") macros) will cover nearly all needs. Some facts:

+ Tectonic is so smooth, it downloads packages automatically, making it great for newcomers. No need to install a heavy #ts-logo("TeX") distribution.
+ #ts-logo("LuaLaTeX") is the only engine that supports both protrusion and font expansion (microtypography) along with Lua scripting, which yields smoother PDF output.
+ #ts-logo("XeLaTeX") has similar results to Tectonic but allows `–shell-escape` for minted code highlighting.
