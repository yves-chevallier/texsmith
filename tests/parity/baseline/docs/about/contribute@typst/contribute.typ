#set document(
title: "Contributing",
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
#text(size: 1.8em, weight: "bold")[Contributing]]
#v(1.5em)

I welcome contributions from the community to help improve TeXSmith! Whether it's reporting bugs, suggesting new features, or submitting code changes, your input is valuable. Here's how you can contribute:

/ Reporting issues: If you encounter any bugs or issues while using TeXSmith, please #link("https://github.com/yves-chevallier/texsmith/issues")[report them].
/ Suggesting features: Have an idea for a new feature or improvement? We'd love to #link("https://github.com/yves-chevallier/texsmith/issues")[hear it]!
/ Submitting code changes: If you'd like to contribute code, please fork the repository, make your changes, and submit a #link("https://github.com/yves-chevallier/texsmith/pulls")[pull request]. Make sure to follow the coding style and include tests for any new functionality.
/ Improving documentation: Help us keep the documentation up-to-date and comprehensive by suggesting edits or additions.
/ Documentation priorities: Check the \[Release Notes\]\[releasenotes\] & Compatibility page and open issues to see which doc sections need attention when the engine evolves.
/ Develop templates: Create and share your own #ts-logo("LaTeX") templates for TeXSmith users to use.

TeXSmith is a newly developed project and is not ready for production use yet, but you can test it out and help us improve it.

= Run the tests

TeXSmith parses and writes through #link("https://github.com/yves-chevallier/tmark")[TMark],
whose wheel is built from a checkout of that repository under `vendor/tmark`
(`[tool.uv.sources]` points at it, and `vendor/tmark` is gitignored). You need a
Rust toolchain, because `maturin` builds the extension module:

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
git clone --branch texsmith-migration \
    https://github.com/yves-chevallier/tmark.git vendor/tmark
uv sync
uv run pytest
```

The CI workflows do exactly this, so a failure here is reproducible there.

= Build the documentation locally

```bash
uv sync --group docs
uv run mkdocs serve
```

= Test CI

To test the Continuous Integration (CI) using GitHub Actions, we need `act` installed on your local machine:

```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
act -j build
```

This would require a *lot* of disk space, as it uses Docker containers to simulate the GitHub Actions environment. Select the _medium_ size image when prompted.
