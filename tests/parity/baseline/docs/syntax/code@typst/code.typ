#set document(
title: "Code",
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
#text(size: 1.8em, weight: "bold")[Code]]
#v(1.5em)

Code fences are one of Markdown’s greatest hits: drop a triple backtick block,
label it, and you get nicely formatted snippets. A fenced code block is the
degenerate case of TMark's #link("index.md#four-syntactic-families")[data-directive family]:
its info string is `<lang> <node>`, and the node word defaults to `code`.

= Code Blocks

You can insert code snippets and specify options in the info string.

- Line numbers with `linenums="1"`
- Title with `title="filename.ext"`
- Highlight specific lines with `hl_lines="2-3"`
- An external source with `include="path/to/file"`

The info string may also end with a full attribute list in braces, which is
where a class or an id lives:

````md
```python {.wide title="hanoi.py"}
print(1)
```
````

The highlighting engine is global, set with `press.code.engine`: `pygments`
(the default, Tectonic-safe), `listings`, `verbatim` or `minted` (which needs
shell escape).

== Name your code blocks

#ts-code(title: [bubble\_sort.py])[
```py
def bubble_sort(items):
    for i in range(len(items)):
        for j in range(len(items) - 1 - i):
            if items[j] > items[j + 1]:
                items[j], items[j + 1] = items[j + 1], items[j]
```]

== Add line numbers

#ts-code(linenums: 1)[
```javascript
function bubbleSort(items) {
    for (let i = 0; i < items.length; i++) {
        for (let j = 0; j < items.length - 1 - i; j++) {
            if (items[j] > items[j + 1]) {
                [items[j], items[j + 1]] = [items[j + 1], items[j]];
            }
        }
    }
}
```]

== Highlight specific lines

#ts-code(hl-lines: ("2-3"))[
```lisp
(defun bubble-sort (items)
  (dotimes (i (length items))
    (dotimes (j (- (length items) 1 i))
      (when (> (nth j items) (nth (+ j 1) items))
        (rotatef (nth j items) (nth (+ j 1) items))))))
```]

== External sources

Put `include=` on the info string to read the code from a file at render time,
keeping samples reusable across docs. The file is never pasted into the source,
so a fence inside it is just text.

````md
```python include="examples/code/bubble_sort.py" title="bubble_sort.py"
```
````

To splice a whole Markdown file into the document instead, use the `include`
role on a line of its own:

```md
{include}(examples/code/bubble_sort.md)
```

The PyMdownX snippet syntax `–8<– "file"` is accepted as deprecated sugar; it
pastes text before parsing, which breaks on nested fences, and it never rebases
relative paths. See Migrating to TMark.

=== Any dash count is the same marker

The marker is PyMdownX's own, `-{2,}8<-{2,}`: *two or more dashes on each
side, the two sides free to differ*. `–8<–`, `—8<—`, `–8<—-` and
`—–8<—–` are one spelling, and none of them is a divider. This matters
because TeXSmith's own corpus writes three dashes throughout: for a long time
only the two-dash form was recognised, so every one of those includes quietly
stayed literal text.

A `;` before the marker is PyMdownX's escape: the line includes nothing and is
the text it spells, less one `;`, with no diagnostic — writing the marker is
not the deprecated act. The rule holds for a fence whose body is one snippet
line, and there the `;` is also what the printer writes, a fence body having no
backslash escape of its own; in a paragraph the printer escapes the literal
marker with a backslash instead.

#table(
columns: 2,
align: (left, left),
table.header([You wrote], [Normal form]),
[`–8<– "chapters/boot.md"`], [`{include}(chapters/boot.md)`],
[`—8<— "chapters/boot.md"`], [`{include}(chapters/boot.md)`],
[a fence body `–8<– "hanoi.py"`], [```` ```python include="hanoi.py" ````],
[`;—8<— "chapters/boot.md"`], [`\—8<— "chapters/boot.md"`],
)

== With #ts-logo("LaTeX") output

Here’s what the above examples look like when rendered with TeXSmith:

#figure(
image("snippet-<HASH>.png", width: 60%),
)

== Captioned listings

A `Listing:` caption line promotes a code block to a numbered, referenceable
listing — the same rule as every other float:

````md
```python title="bubble_sort.py"
def bubble_sort(items): ...
```

Listing: Bubble sort, naive version. {#lst:bubble}

@lst:bubble is quadratic in the worst case.
````

= Inline Code

You can also include inline code snippets using backticks `` ` `` like this:

== Unformatted

```markdown
To sort a list in Python, you can use the `sorted()` function.
```

It will simply be rendered as monospaced text in #ts-logo("LaTeX"):

```
To sort a list in Python, you can use the \texttt{sorted()} function.
```

== Highlighted

Inline code can also be highlighted. The canonical spelling is the `code` role,
whose positional argument is the language; the PyMdownX `#!lang` shebang is
sugar for the same node.

```md
You can use {code py}[print("Hello, World!")] to display a message in Python.

You can use `#!py print("Hello, World!")` to display a message in Python.
```

With TeXSmith this example renders as follows:

```markdown
# Inline Code

In C the `strstr` function defined with the prototype
{code lang=c}[char *strstr(const char *haystack, const char *needle);] is
used to locate a substring within a string. It returns a pointer to the first occurrence of the substring
`needle` in the string `haystack`, or `NULL` if the substring is not found.

In Python, you can achieve similar functionality using the `find` method of strings for example: {code lang=python}[haystack.find(sub: int) -> int]. This method returns the lowest index of the substring if found in the string, otherwise it returns `-1`.
```

#figure(
image("snippet-<HASH>.png"),
)
