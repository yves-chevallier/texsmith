# Tectonic Engine

Tectonic is the default PDF engine in TeXSmith. It bundles automatic package
fetching, fast incremental builds, and minimal setup -- ideal for CI pipelines and
lightweight containers. You can switch to `latexmk` with `--engine lualatex` or
`--engine xelatex` when you need full control of the traditional toolchain.

## Install Tectonic

- **macOS:** `brew install tectonic`
- **Ubuntu/Debian:** `sudo apt install tectonic` (or `cargo install tectonic`)
- **Fedora:** `sudo dnf install tectonic`
- **Windows:** `scoop install tectonic` or `choco install tectonic`
- **Fallback:** grab a prebuilt archive from <https://tectonic-typesetting.github.io/> and put
  the `tectonic` binary on your `PATH`.

After installation, run `tectonic --version` to confirm the binary is available.

## Building with Tectonic

- CLI: `texsmith notes.md --template article --build` uses Tectonic automatically.
- Latexmk: add `--engine lualatex` (or `--engine xelatex`) to opt into the latexmk +
  `.latexmkrc` flow.
- API: call `ConversionService.build_pdf(render_result, engine="tectonic")` after
  rendering a template.

TeXSmith still checks for optional helpers -- `biber`, `makeindex`/`texindy`,
`makeglossaries` -- and reports anything missing before the engine runs.
