# Cooking Recipes

TeXSmith can be used to write cooking recipes with professional formatting from
a YAML description and a custom template.

Here a delicious cake recipe rendered using TeXSmith. Click the image to download the PDF.

[![Recipe preview](../assets/examples/recipe.png){width=60%}](../assets/examples/recipe.pdf)

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

