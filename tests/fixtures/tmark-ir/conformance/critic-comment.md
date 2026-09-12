# Critic markup: comment

Spec Appendix "PyMdownX compatibility profile", §Comment, challenge C49:
`{>>note<<}` holds a reviewer's note. It lowers to the `Comment` §Comment
names, inside a `Span{.critic}`: the class is what separates a note written
*for* a reviewer from an author's `<!-- … -->`, which every backend strips.
The paged backends typeset the annotation (`\tscomment{…}`, `#ts-comment[…]`)
— a review PDF that hid it would be pointless — and the web writer emits a
zero-width span carrying the text, so a published page shows nothing.

## input

```md
The proof holds. {>>cite Knuth here<<}
```

## canonical

```md
The proof holds. {>>cite Knuth here<<}
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
          "text": "The proof holds. "
        },
        {
          "type": "Span",
          "content": [
            {
              "type": "Comment",
              "text": "cite Knuth here"
            }
          ],
          "attrs": {
            "classes": [
              "critic"
            ]
          }
        }
      ]
    }
  ]
}
```

## latex

```latex
The proof holds. \tscomment{cite Knuth here}
```

## typst

```typst
The proof holds. #ts-comment[cite Knuth here]
```

## html

```html
<p>The proof holds.<span class="critic comment" data-comment="cite Knuth here"></span></p>
```
