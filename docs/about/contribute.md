# Contributing

I welcome contributions from the community to help improve TexSmith! Whether it's reporting bugs, suggesting new features, or submitting code changes, your input is valuable to us. Here's how you can contribute:

Reporting Issues
: If you encounter any bugs or issues while using TexSmith, please [report them](https://github.com/yves-chevallier/texsmith/issues).

Suggesting Features
: Have an idea for a new feature or improvement? We'd love to [hear it](https://github.com/yves-chevallier/texsmith/issues)!

Submitting Code Changes
: If you'd like to contribute code, please fork the repository, make your changes, and submit a [pull request](https://github.com/yves-chevallier/texsmith/pulls). Make sure to follow the coding style and include tests for any new functionality.

Improving Documentation
: Help us keep the documentation up-to-date and comprehensive by suggesting edits or additions.

Documentation priorities
: Check the [Release Notes][releasenotes] & Compatibility page and open issues to see which doc sections need attention when the engine evolves.

Develop Templates
: Create and share your own LaTeX templates for TexSmith users to utilize.

TeXSmith is a newly developed project, and is not ready for production use yet, but you can test it out and help us improve it.

## Run the tests

```bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
uv sync
uv run pytest
```

## Build the documentation locally

```bash
uv sync --group docs
uv run mkdocs serve
```

## Test CI

To test the Continuous Integration (CI) using GitHub Actions, we need `act` installed on your local machine:

```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
git clone https://github.com/yves-chevallier/texsmith.git
cd texsmith
act -j build
```

This would require a **lot** of disk space, as it uses Docker containers to simulate the GitHub Actions environment. Select the *medium* size image when prompted.
