# Diagrams

This example demonstrates how you can integrate [Mermaid](https://mermaid.js.org/) and [Draw.io](https://app.diagrams.net/) diagrams in your documentation.

Both tools are very useful to avoid binary assets and keep Git diffs manageable. Take for example this code:

````markdown
--8<--- "examples/diagrams/diagrams.md"
````

## Rendered Markdown

Here what it looks like when rendered in MkDocs:

--8<--- "examples/diagrams/diagrams.md"

## PDF

And here is how it looks in the generated PDF:

````md {.snippet data-caption="Download PDF" data-frame="true" data-width="60%"}
---8<--- "examples/diagrams/diagrams.md"
````
