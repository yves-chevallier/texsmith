#set document(
title: "Letters",
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
#text(size: 1.8em, weight: "bold")[Letters]]
#v(1.5em)

TeXSmith includes a built-in letter template based on the KOMA-Script `scrlttr2` class. Below are three examples of letters formatted according to different national standards: *DIN* (Germany), *SN* (Switzerland), and *NF* (France).

The letter template is built into TeXSmith; to use it, set `-tletter` on the command line or `template: letter` in your document front matter.

#ts-div("tab", title: "DIN (Germany)")[
#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Download PDF],
)]

#ts-div("tab", title: "SN (Switzerland)")[
#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Download PDF],
)]

#ts-div("tab", title: "NF (France)")[
#figure(
image("snippet-<HASH>.png", width: 70%),
caption: [Download PDF],
)]

Here is the source code for the letter example used above:

#ts-div("tab", title: "Letter")[
```markdown
---
press:
  template: letter
  date: 1903-07-14
  signature: marie-curie.svg
  back-address: Laboratory of Physics and Chemistry, Sorbonne Univ., Paris
  from:
    name: Marie Skłodowska Curie
    address: |
      Laboratory of Physics and Chemistry
      Sorbonne University
      75005 Paris, France
  to:
    name: Leonardo da Vinci
    address: |
      Casa di Leonardo
      Near the Church of Santa Croce
      Florence, Republic of Florence (c. 1500)
  ps: |
    How did you manage to withstand the ravages of time?
    You should have been dead for 384 years by now.
---
# Dear Maestro Leonardo

I have received your latest letter—delivered, I assume, by whatever ingenious flying
machine you are currently testing—and feel compelled to clarify a few scientific
misunderstandings before you accidentally remove yourself from the timeline.

First, while your enthusiasm for "radiant essences" is admirable, radioactivity is
not a universal power source. Your idea for a "self-illuminating mechanical bird,
animated by glowing stones" is creative, but such stones would send you flying only
toward the afterlife. Please wear gloves—preferably very thick ones.

Second, I examined the sketch you enclosed, a contraption somewhere between a windmill,
a cauldron, and an umbrella. I cannot determine its purpose, but I urge caution. If it
is meant to rotate, do not sit inside it. If it is meant to boil, do not sit inside it.
If it is meant to do both… absolutely do not sit inside it.

Lastly, you asked whether radioactive materials might accelerate human creativity.
A flattering thought, but the glow around me is scientific, not -- as you
suggested -- "proof of a supernatural muse." Should you begin to glow,
I advise stepping away quickly.

I remain deeply impressed by your mind, your sketches, and your relentless curiosity.
Should you need help with physics—or with identifying substances that should not go
into flying machines—I remain at your service.

With great scientific affection,
```]

#ts-div("tab", title: "Template")[
```latex
\documentclass[
  paper=a4,
  parskip=half,
  firstfoot=false,
  enlargefirstpage=true,
]{scrlttr2}
\usepackage{xcolor}
\definecolor{texsmithLinkColor}{HTML}{0B3D91}
\VAR{extra_packages}
% Contract macros (fragment-contracts.md §4): a letter keeps its callouts
% flat — a thin rule on the left, no rounded frame — by restyling the
% tscallout box through its pgfkeys family. Guarded: ts-callouts is only
% loaded when the document has a callout.
\ifcsname tscallout\endcsname
  \tcbset{/ts/callout/.append style={arc=0mm, boxrule=0mm, frame hidden, borderline west={0.3mm}{0mm}{black!70}}}
\fi
\usepackage{graphicx}
\usepackage[\VAR{babel_language|default('english')}]{babel}
\usepackage[
    colorlinks=true,
    linkcolor=texsmithLinkColor,
    urlcolor=texsmithLinkColor,
    citecolor=texsmithLinkColor]{hyperref}
\LoadLetterOption{\VAR{letter_standard_option}}
\KOMAoptions{foldmarks=\VAR{foldmarks_option}}
\BLOCK{ set margin_style = margin|default('default')|lower }
\BLOCK{ set margin_literal = margin_style not in ["narrow", "default", "wide"] }
\BLOCK{ if margin_style == "narrow" }
\KOMAoptions{fromalign=left, backaddress=false}
\setlength{\oddsidemargin}{1cm}
\BLOCK{ elif margin_style == "wide" }
\KOMAoptions{fromalign=left, backaddress=false}
\setlength{\oddsidemargin}{2cm}
\BLOCK{ elif margin_literal }
\KOMAoptions{fromalign=left, backaddress=false}
\setlength{\oddsidemargin}{0cm}
\addtolength{\textwidth}{-\VAR{margin}}
\BLOCK{ endif }
\BLOCK{ if use_cursive_signature }
\setmainfont[Path=fonts/,Extension=.otf,Ligatures=Common,Mapping=]{modernline}
\newcommand{\TexsmithLetterEndash}{\kern0.05em-\kern0.05em}
\newcommand{\TexsmithLetterEmdash}{\kern0.05em-\kern0.05em-\kern0.05em}
\catcode"2013=\active
\catcode"2014=\active
\begingroup\lccode`~="2013\lowercase{\endgroup\protected\def~}{\TexsmithLetterEndash}
\begingroup\lccode`~="2014\lowercase{\endgroup\protected\def~}{\TexsmithLetterEmdash}
\BLOCK{ endif }

\BLOCK{ if preamble }
% Custom document preamble injected from overrides.
\VAR{preamble}

\BLOCK{ endif }

\BLOCK{ if use_cursive_signature }
\newfontfamily\SignatureFont[Path=fonts/,Extension=.otf]{modernline}
\newcommand{\SignatureText}[1]{{\SignatureFont #1}}
\BLOCK{ else }
\newcommand{\SignatureText}[1]{#1}
\BLOCK{ endif }

\newcommand{\SignatureBlock}{%
\BLOCK{ if has_signature_image }
  \includegraphics[height=1.6cm]{\VAR{signature_image_path}}
  \\[-0.25\baselineskip]%
\BLOCK{ endif }
  \SignatureText{\VAR{signature_text}}%
}

\setkomavar{fromname}{\VAR{from_name}}
\setkomavar{fromaddress}{%
\BLOCK{ if has_sender_address }
  \VAR{from_address_lines|join('\\\\\n')}
\BLOCK{ endif }
}
\BLOCK{ if from_location_value -}
\setkomavar{location}{\VAR{from_location_value}}\BLOCK{ endif }
\BLOCK{ set effective_date = date_value|default('')|trim }
\setkomavar{date}{\BLOCK{ if effective_date -}
\VAR{date_value}\BLOCK{ else }\today\BLOCK{ endif }}
\BLOCK{ if has_subject }
\setkomavar{subject}{\VAR{object_value}}
\setkomavar*{subject}{\VAR{subject_prefix}}
\BLOCK{ endif }
\setkomavar{signature}{\SignatureBlock}
\BLOCK{ if has_back_address }
\setkomavar{backaddress}{%
  \VAR{back_address_lines|join('\\\\\n')}
}
\BLOCK{ endif }
\BLOCK{ if reference_value }
\setkomavar{myref}{\VAR{reference_value}}
\BLOCK{ endif }
\BLOCK{ if not reference_fields_enabled }
\removereffields
\BLOCK{ endif }
\renewcommand*{\raggedsignature}{\VAR{signature_alignment_command}}

\begin{document}

\begin{letter}{%
\BLOCK{ if has_recipient_address }
  \VAR{to_address_lines|join('\\\\\n  ')}
\BLOCK{ else }
  \VAR{to_name}
\BLOCK{ endif }
}

\opening{\VAR{opening_text}}

\VAR{mainmatter}

\VAR{backmatter}
\VAR{fragment_backmatter}

\BLOCK{ if has_closing }
\closing{\VAR{closing_text}}
\BLOCK{ endif }
\BLOCK{ if has_postscript }
\ps{PS: \VAR{postscript_text}}
\BLOCK{ endif }

\end{letter}
\BLOCK{ if not page_numbers }
\pagenumbering{gobble}
\thispagestyle{empty}
\pagestyle{empty}
\BLOCK{ endif }

\end{document}
```]

#ts-div("tab", title: "Manifest")[
```toml
[compat]
texsmith = ">=0.6,<1.0"

[latex.template]
name = "formal-letter"
version = "0.1.0"
entrypoint = "template/template.tex"
engine = "xelatex"
shell_escape = false
texlive_year = 2023
tlmgr_packages = [
    "babel",
    "fontspec",
    "microtype",
    "koma-script",
]
description = """
Formal letter template based on KOMA-Script with configurable
sender/recipient and standards."""

fragments = [
    "ts-fonts",
    "ts-extra",
    "ts-keystrokes",
    "ts-callouts",
    "ts-code",
    "ts-glossary",
    "ts-bibliography",
    "ts-todolist",
]

[latex.template.attributes.cursive]
default = false
type = "boolean"
sources = ["cursive"]
description = "Toggle cursive signature font."

[latex.template.attributes.language]
default = "en-UK"
type = "string"
allow_empty = false
sources = ["language"]
description = "Language for babel."

[latex.template.attributes.standard]
default = ""
type = "string"
sources = ["standard", "format"]
description = "Letter standard/format (e.g., sn, nf)."

[latex.template.attributes.date]
default = ""
type = "string"
escape = "latex"
allow_empty = true
sources = ["date"]

[latex.template.attributes.object]
default = ""
type = "string"
escape = "latex"
sources = ["object"]
description = "Subject line."

[latex.template.attributes.from_name]
default = ""
type = "string"
escape = "latex"
allow_empty = false
required = true
sources = ["from_name"]
description = "Sender full name."

[latex.template.attributes.from_address]
default = []
type = "list"
sources = ["from_address"]

[latex.template.attributes.back_address]
default = ""
type = "string"
escape = "latex"
sources = ["back_address"]

[latex.template.attributes.from_location]
default = ""
type = "string"
escape = "latex"
sources = ["from_location"]

[latex.template.attributes.to_name]
default = ""
type = "string"
escape = "latex"
allow_empty = false
required = true
sources = ["to_name"]
description = "Recipient full name."

[latex.template.attributes.to_address]
default = []
type = "list"
sources = ["to_address"]

[latex.template.attributes.closing]
default = ""
type = "string"
escape = "latex"
sources = ["closing"]
description = "Closing phrase."

[latex.template.attributes.opening]
default = ""
type = "string"
escape = "latex"
sources = ["opening"]
description = "Opening phrase."

[latex.template.attributes.signature]
default = ""
type = "any"
sources = ["signature"]
description = "Signature block (text or raw LaTeX)."

[latex.template.attributes.source_dir]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["source_dir"]

[latex.template.attributes.output_dir]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["output_dir"]

[latex.template.attributes.signature_align]
default = "left"
type = "string"
sources = ["signature_align"]

[latex.template.attributes.reference]
default = ""
type = "string"
escape = "latex"
sources = ["reference"]
description = "Reference field content."

[latex.template.attributes.reference_fields]
default = false
type = "boolean"
sources = ["reference_fields"]
description = "Whether to render reference fields block."

[latex.template.attributes.postscript]
default = ""
type = "string"
escape = "latex"
sources = ["postscript"]
description = "Postscript paragraph."

[latex.template.attributes.fold_marks]
default = false
type = "boolean"
sources = ["fold_marks"]
description = "Toggle fold marks."

[latex.template.attributes.margin]
default = "default"
type = "string"
normaliser = "margin_style"
sources = ["margin"]
description = "Margin style (default, wide, narrow)."

[latex.template.attributes.preamble]
default = ""
type = "string"
allow_empty = true
sources = ["preamble"]

[latex.template.attributes.page_numbers]
default = false
type = "boolean"
sources = ["page_numbers"]
description = "Enable page numbers."

[latex.template.slots.mainmatter]
default = true
base_level = 10
strip_heading = true

[latex.template.slots.backmatter]
strip_heading = true

[latex.template.assets]
"fonts/modernline.otf" = { source = "fonts/modernline.otf" }

# --------------------------------------------------------------------------- #
# Typst backend: a clean business-letter layout. The LaTeX backend's KOMA-Script
# national standards (DIN/SN/NF) collapse to a single Typst layout; sender /
# recipient blocks read the nested ``from`` / ``to`` front matter directly.
# --------------------------------------------------------------------------- #
[typst.template]
name = "formal-letter"
version = "0.1.0"
entrypoint = "template/template.typ"

[typst.template.attributes.language]
default = "en"
type = "string"
allow_empty = false
normaliser = "bcp47_language"
sources = ["language", "lang"]

[typst.template.attributes.from_name]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["from.name", "from_name"]

[typst.template.attributes.from_address]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["from.address", "from_address"]

[typst.template.attributes.to_name]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["to.name", "to_name"]

[typst.template.attributes.to_address]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["to.address", "to_address"]

[typst.template.attributes.date]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["date"]

[typst.template.attributes.back_address]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["back-address", "back_address"]

[typst.template.attributes.signature]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["signature"]

[typst.template.attributes.postscript]
default = ""
type = "string"
allow_empty = true
format = "raw"
sources = ["ps", "postscript"]

[typst.template.slots.mainmatter]
default = true
strip_heading = true
```]

To build the examples, use the following commands:

```bash
texsmith letter.md --build # for default format (DIN)
texsmith letter.md --build -aformat sn  # for SN format
texsmith letter.md --build -aformat nf  # for NF format
```

= Standards

== DIN 5008

Among all existing standards, *DIN 5008* is by far the most widely adopted reference for business correspondence in Germany. It prescribes layout rules, font sizes, margins, and a whole constellation of formatting details to guarantee consistency and professionalism in written communication. It is quite possibly the most detailed standard of its kind, specifying exact margin dimensions, the precise positioning of address blocks, the full structural blueprint of a professional letter, and fine-grained typographic conventions.

I haven’t personally dived into the full paid specification, but it’s safe to assume that KOMA-Script’s letter template draws heavily from it—and by extension, so does TeXSmith.

== NF Z 11-001

The former French AFNOR standard *NF Z 11-001*, replaced by ISO 269 back in 1998, defined the presentation rules for administrative letters in France. It described margins, address placement, letter structure, and typographic conventions intended to ensure clarity and uniformity in official documents. Although the standard is no longer active, it has left a lasting imprint on French administrative writing practices, and echoes of it can still be found in contemporary templates.

== ISO 214

*ISO 214* is an international standard specifying the layout conventions for commercial letters. It defines margins, address placement, structural order, and typographic rules to ensure a clear and professional presentation of business correspondence across borders. Its purpose is to harmonize commercial letter-writing practices between countries, smoothing out differences and making international communication a little more predictable.

= Why We Ultimately Chose scrlttr2

While our documentation already covers the underlying standards that govern letter layout, what actually matters in practice is finding a tool that can embody these rules with precision, consistency, and a healthy respect for typographic sanity. This is the point where #ts-logo("LaTeX")—and specifically KOMA-Script’s `scrlttr2`—quietly distinguishes itself from the rest. Designed in the German tradition of rigorous typesetting, `scrlttr2` follows the logic of formal letter standards with an almost pedantic accuracy, offering a layout engine that behaves predictably and stays faithful to the structural constraints imposed by modern correspondence norms. Yet it remains flexible enough to emulate the conventions of other national styles without falling apart or requiring awkward hacks.

In short, choosing `scrlttr2` was less about tradition and more about engineering. It gives us a letter typesetting engine that is standards-aware, robust enough for large-scale automation, and structured enough to keep our layouts consistent across contexts. It is not the easiest tool, nor the most forgiving, but for anyone who values correctness, longevity, and the quiet satisfaction of seeing a letter snap perfectly into place, it is simply the right one.

= Build the exemple locally

To build the letter example locally, navigate to the `examples/letter` directory and run the following command:

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
uv sync
cd examples/letter
make
```
