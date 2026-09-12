# Divider

Spec §HorizontalRule: `---` is a `HorizontalRule`. At the top level of the
document the LaTeX writer emits `\tsdivider`, the Typst writer
`#ts-divider()` (a page break by default, redefinable by the template), the
HTML writer `<hr>`. Inside a container — here a block quote — the same node
is a separator, not a page break: `\tsrule`, `#ts-rule()`, `<hr class="rule">`
(challenge C48; Typst rejects a page break inside a container outright).

## input

```md
First page.

---

Second page.

> Before the rule.
>
> ---
>
> After the rule.
```

## canonical

```md
First page.

---

Second page.

> Before the rule.
>
> ---
>
> After the rule.
```

## ir

```json
{
  "blocks": [
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "First page."
        }
      ]
    },
    {
      "type": "HorizontalRule"
    },
    {
      "type": "Para",
      "content": [
        {
          "type": "Str",
          "text": "Second page."
        }
      ]
    },
    {
      "type": "BlockQuote",
      "content": [
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "Before the rule."
            }
          ]
        },
        {
          "type": "HorizontalRule"
        },
        {
          "type": "Para",
          "content": [
            {
              "type": "Str",
              "text": "After the rule."
            }
          ]
        }
      ]
    }
  ]
}
```

## latex

```latex
First page.

\tsdivider

Second page.

\begin{displayquote}
Before the rule.

\tsrule

After the rule.
\end{displayquote}
```

## typst

```typst
First page.

#ts-divider()

Second page.

#quote(block: true)[
Before the rule.

#ts-rule()

After the rule.
]
```

## html

```html
<p>First page.</p>
<hr />
<p>Second page.</p>
<blockquote>
<p>Before the rule.</p>
<hr class="rule" />
<p>After the rule.</p>
</blockquote>
```
