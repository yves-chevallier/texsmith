# Global user's configuraiton

We want texsmith to support a global user configuration file located at `.texsmith/config.yml`. This file allows users to set their preferred defaults for templates, Mermaid styles, compilation options, and paper formats. The configuration file is optional and can be placed in the current working directory or any parent directory.

This does only affect the CLI usage of TeXSmith. The API still remains robust and does not depend on any global configuration, except for the cache directory.

A config file could be:

```yaml
template: article
engine: tectonic
paper:
  format: a4
  orientation: portrait
mermaid:
  theme: neutral
callouts:
  style: fancy
```

The format is not rigidly defined. It is used to set default values for command-line options. Command-line options always take precedence over configuration file settings and YAML front matter in Markdown files have the highest precedence.

Fragments and plugins, and everything inherit from this global configuration when using the CLI.
