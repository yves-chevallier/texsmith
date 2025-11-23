# Cooking Recipes

TeXSmith isn’t just for papers and slides -- it can plate up gorgeous recipes straight from structured data. Here’s a French walnut cake expressed as YAML, pushed through a custom `recipe` template. Click the card to grab the PDF.

```yaml {.snippet data-caption="Demo" data-frame="true" data-width="60%" data-template="../../examples/recipe"}
---8<--- "examples/recipe/cake.yml"
```

The authoring surface is pure data: **YAML** fields flow into a LaTeX template, no Markdown gymnastics required. Swap the YAML for a DB/API payload and you’ve got a pipeline-ready recipe generator for your site or app.

=== "cake.yml"

    ```yaml
    ---8<--- "examples/recipe/cake.yml"
    ```

=== "manifest.toml"

    ```toml
    --8<--- "examples/recipe/manifest.toml"
    ```

=== "template.tex"

    ```tex
    ---8<--- "examples/recipe/template.tex"
    ```

!!! note

    The way of representing the recipe in the template was inspired from the "Cours de cuisine" from M.-C. Bolle in 1978. She wrote an extraordinary book on cooking recipes for the "Department d'instruction publique" of the Canton of Geneva, Switzerland.

    I've never seen such way of writing recipes elsewhere, but I find it very practical and efficient.
