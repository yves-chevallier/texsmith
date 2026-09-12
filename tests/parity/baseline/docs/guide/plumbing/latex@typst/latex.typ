#set document(
title: "LaTeX",
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
#text(size: 1.8em, weight: "bold")[LaTeX]]
#v(1.5em)

#ts-logo("LaTeX") is the layer that turned #ts-logo("TeX") from a brilliant but arcane typesetting engine into a real document preparation system. Where #ts-logo("TeX") gives you microscopic control of every typographic atom, #ts-logo("LaTeX") gives you structure, meaning, and reusable design. It’s the difference between soldering your own circuit board and using a well-designed development kit: the power is still there, but now it’s ergonomic, consistent, and scalable. Over the decades, #ts-logo("LaTeX") has become the lingua franca of academic publishing, math-heavy documents, and anyone who appreciates the elegance of markup-driven writing.

= Leslie Lamport

Leslie Lamport, an American computer scientist best known for his pioneering work in distributed systems and formal methods, created #ts-logo("LaTeX") in the early 1980s while at SRI International. Frustrated by the repetitiveness and fragility of raw #ts-logo("TeX") macros, Lamport designed #ts-logo("LaTeX") as a higher-level interface where authors declare what a document element is—"this is a theorem," "this is a section," "this is a quotation"—and let the underlying macros decide how it should look. Lamport’s disciplined, engineering-driven approach gave #ts-logo("LaTeX") the structure and style consistency that made it indispensable across scientific disciplines. Though others have maintained and extended #ts-logo("LaTeX") since, Lamport remains the architect of the system that made #ts-logo("TeX") widely accessible.

= How #ts-logo("LaTeX") differs from #ts-logo("TeX")

#ts-logo("TeX") is a typesetting engine, essentially a low-level programming language for shaping glyphs and boxes in beautifully precise ways. #ts-logo("LaTeX") sits on top of it as a macro format and workflow philosophy. Where #ts-logo("TeX") wants you to manage fonts, spacing, and layout directly, #ts-logo("LaTeX") encourages "semantic markup": writing with meaning and structure rather than appearance. #ts-logo("TeX") says "place this box 2 pt to the right and apply this italic correction"; #ts-logo("LaTeX") says "this is a subsection header; I’ll handle the aesthetics." #ts-logo("LaTeX") also provides standardized environments, robust cross-referencing, bibliographies, floating figures, and a massive ecosystem of packages. In short, #ts-logo("TeX") is the engine; #ts-logo("LaTeX") is the operating system built on top of it.

= Legacy

#ts-logo("LaTeX")’s legacy is enormous. It transformed #ts-logo("TeX") from a typographic laboratory into a practical tool used by millions. It standardized academic publishing workflows, made mathematical writing accessible, and proved that declarative document design could outlive trends in software and UI. From the original #ts-logo("LaTeX") 2.09 to today’s actively developed #ts-logo("LaTeX2e") and the upcoming LaTeX3 paradigm, the system continues to evolve while staying compatible with decades of documents. Its influence goes beyond typesetting: #ts-logo("LaTeX") shaped how scientists write, how publishers structure content, and how digital typography is conceptualized. It remains one of the rare pieces of software whose output is expected to remain stable across generations.
