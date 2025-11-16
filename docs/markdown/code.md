# Code

Code blocks is one of the key features of Markdown, it allows to highlight code snippets in various programming languages. TeXSmith uses `minted` package to provide syntax highlighting in LaTeX output. While `minted` is usually slower than other packages like `listings`, it offers superior highlighting quality and supports a wide range of programming languages, moreover the Unicode support is better when built with `xelatex` or `lualatex`.

## Code Blocks

You can insert code snippets and specify options for syntax highlighting.

- Line numbers with `linenums="1"`
- Title with `title="filename.ext"`
- Highlight specific lines with `hl_lines="2-3"`

### Name your code blocks

``` py title="bubble_sort.py"
def bubble_sort(items):
    for i in range(len(items)):
        for j in range(len(items) - 1 - i):
            if items[j] > items[j + 1]:
                items[j], items[j + 1] = items[j + 1], items[j]
```

### Add line numbers

``` javascript linenums="1"
function bubbleSort(items) {
    for (let i = 0; i < items.length; i++) {
        for (let j = 0; j < items.length - 1 - i; j++) {
            if (items[j] > items[j + 1]) {
                [items[j], items[j + 1]] = [items[j + 1], items[j]];
            }
        }
    }
}
```

### Highlight specific lines

``` lisp hl_lines="2-3"
(defun bubble-sort (items)
  (dotimes (i (length items))
    (dotimes (j (- (length items) 1 i))
      (when (> (nth j items) (nth (+ j 1) items))
        (rotatef (nth j items) (nth (+ j 1) items))))))
```

### Snippets

With the `pymdownx.snippets` extension, you can include external code snippets stored in separate files. This is useful for reusing code across multiple documents.

```` markdown
```python
;--8<-- "examples/code/bubble_sort.py"
```
````

!!! tip
    If using MkDocs, ensure that the `base_path` for snippets is correctly set in your configuration to point to the directory containing your code files.

    A safe configuration would be:

    ```yaml
    - pymdownx.snippets:
        check_paths: true
        base_path: !relative $config_dir    
    ```

### With LaTeX output

Here what the above examples would look when rendered with TeXSmith:

[![Code Block Examples in LaTeX](../assets/examples/code-block.png)](../assets/examples/code-block.pdf)

## Inline Code

You can also include inline code snippets using backticks `` ` `` like this:

### Unformatted

```markdown
To sort a list in Python, you can use the `sorted()` function.
```

It will simply be rendered as monospaced text in LaTeX:

```text
To sort a list in Python, you can use the \texttt{sorted()} function.
```

### Highlighted

Inline code can also be highlighted thanks to the Pymdownx `inlinehilite` extension.

```markdown
You can use `` `#!py print("Hello, World!")` `` to display a message in Python.

> You can use `#!py print("Hello, World!")` to display a message in Python.
```

With TeXSmith this example will be rendered as follow:

```markdown
--8<-- "examples/code/code-inline.md"
```

[![Inline Code Example in LaTeX](../assets/examples/code-inline.png)](../assets/examples/code-inline.pdf)