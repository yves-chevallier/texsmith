# Emoji Support

TeXSmith supports rendering emojis in Markdown documents. You can include emojis using standard Unicode characters.

By default TeXSmith generates a PDF artifact, but LaTeX packages such as `fontspec` with symbola or `Noto Color Emoji` can also render emojis without external images.

Article template can render emojis using different approachs depending on the emoji attribute settings:

`artifact`
: Embeds emojis as images in the PDF artifact.

`symbola`
: Renders emojis using the Symbola font (Black and white).

`color`
: Renders emojis using the Noto Color Emoji font.

| Emoji | Description                    |
| ----- | ------------------------------ |
| 😊  | Smiling face with smiling eyes |
| 🚀  | Rocket                         |
| 🍕  | Pizza                          |
| 🎉  | Party popper                   |
| 🐍  | Snake                          |
| 🌍  | Globe showing Europe-Africa    |
| 💻  | Laptop computer                |
| 📚  | Books                          |
| 🎨  | Artist palette                 |
| 👽  | Alien                          |
| 👋  | Waving hand                    |
| 🤖  | Robot                          |
| 🦄  | Unicorn                        |
| 🧠  | Brain                          |
| 🛸  | Flying saucer                  |
| 🛰️  | Satellite                     |
| 🐙  | Octopus                        |
