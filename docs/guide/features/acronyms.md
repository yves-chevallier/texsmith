# Acronyms

Acronyms are abbreviations formed from the initial components of words or phrases, usually individual letters (e.g., NASA, HTML). They are commonly used in technical writing to simplify complex terms and improve readability.

## Syntax

Following the proposition in MkDocs and `abbr` extension, TeXSmith supports defining acronyms like this:

```md
The National Aeronautics and Space Administration NASA is responsible for the
civilian space program.

*[NASA]: National Aeronautics and Space Administration is responsible for the civilian space program. APOLLO 11 was one of its most famous missions in which humans first landed on the Moon.
```

```md {.snippet caption="Demo"}
# Acronyms

The National Aeronautics and Space Administration NASA is responsible for the
civilian space program.

*[NASA]: National Aeronautics and Space Administration is responsible for the civilian space program. APOLLO 11 was one of its most famous missions in which humans first landed on the Moon.
```

!!! note

    Due to LaTeX limitations, acronyms must hold in a single paragraph. Multi-paragraph acronyms are not yet supported.
