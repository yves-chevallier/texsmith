# Cooking Recipes

TeXSmith isn’t just for papers and slides -- it can plate up gorgeous recipes straight from structured data. Here’s a French walnut cake expressed as YAML, pushed through a custom `recipe` template. Click the card to grab the PDF.

```yaml {.snippet caption="Demo"}
width: 60%
fragments:
  ts-frame:
press:
  frame: true
cwd: ../../examples/recipe
sources:
  - cake.yml
template: ../../examples/recipe
```

The authoring surface is pure data: **YAML** fields flow into a LaTeX template, no Markdown gymnastics required. Swap the YAML for a DB/API payload and you’ve got a pipeline-ready recipe generator for your site or app.

=== "cake.yml"

    ```yaml
    ---8<--- "examples/recipe/cake.yml"
    ```

=== "manifest.toml"

    ```toml
    ---8<--- "examples/recipe/manifest.toml"
    ```

=== "template.tex"

    ```tex
    ---8<--- "examples/recipe/template.tex"
    ```

!!! note

    The recipe layout used in this template was inspired by the Cours de cuisine created by M.-C. Bolle back in 1978. She produced an exceptional cookbook for the Department of Public Instruction of the Canton of Geneva, Switzerland.

    I’ve never seen recipes presented quite this way anywhere else -- it’s a uniquely clever system -- but I find it incredibly practical and efficient.
