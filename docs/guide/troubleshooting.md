# Troubleshooting LaTeX Builds

Running `texsmith --build` shells out to your selected engine (Tectonic by default, `latexmk` when `--engine` is set to `xelatex`/`lualatex`), `bibtex`/`biber`, and any template assets declared in `manifest.toml`. When those tools fail, the CLI will highlight the failing step and (optionally) open the log file. Use this page to decode the most common issues.

## Enable rich diagnostics

- Add `-v` or `-vv` to surface structured diagnostics from the conversion pipeline (missing slots, unresolved citations, asset copy failures).
- Pass `--debug` to print full Python tracebacks if TeXSmith itself throws.
- Combine `--classic-output` with CI logs when you need deterministic engine output, or keep the default rich output locally for incremental updates.
- When the engine exits non-zero, re-run with `--open-log` to jump directly into the `.log` file.

## latexmk not found

**Symptom:** `latexmk: command not found` or TeXSmith reports it cannot spawn the binary.

**Fix:** Ensure your TeX Live/MacTeX/MiKTeX distribution added `latexmk` to `PATH`. On macOS, `eval "$(/usr/libexec/path_helper -s)"` after installing MacTeX. On Windows, open the “LaTeX apps” PowerShell and run TeXSmith from there.

## tectonic not found

**Symptom:** `tectonic: command not found` or TeXSmith reports missing dependencies before starting the build.

**Fix:** Install Tectonic from your package manager (`brew install tectonic`, `apt install tectonic`, or `cargo install tectonic`) or download a prebuilt binary from https://tectonic-typesetting.github.io/. Ensure the `tectonic` executable is on `PATH` before re-running TeXSmith. You can also switch to `--engine lualatex`/`xelatex` to keep using `latexmk`.

## Missing tlmgr packages

**Symptom:** `LaTeX Error: File <package>.sty not found`.

**Fix:** Run `texsmith --template <NAME> --template-info` and install the listed tlmgr packages (`tlmgr install ...`). Distributions with minimal profiles (BasicTeX, MikTeX) require this step for every template.

## Shell-escape blocked

**Symptom:** `shell escape feature is not enabled` when templates run `minted`, `gnuplot`, or diagram converters.

**Fix:** `texsmith --template-info` indicates whether `shell_escape` is required. Re-run `texsmith --build --classic-output` to confirm the flag. With `--engine lualatex`/`xelatex`, edit your TeX Live config or pass `latexmk -shell-escape` by exporting `LATEXMKOPT="-shell-escape"`. If you're using Tectonic, switch to `--engine lualatex` when you need tighter control over `-shell-escape`.

## Bibliography failures

**Symptom:** `biber`/`bibtex` errors such as `I couldn't open database file` or duplicate citation keys.

**Fix:**

- Run `texsmith references.bib --list-bibliography` to validate files before building.
- Make sure every bibliography file you pass as input exists and is UTF-8 encoded.
- If `biber` complains about encoding, add `encoding = "UTF-8"` to your template manifest bibliography section or normalise via `pybtex`.

## Figures or diagrams missing

**Symptom:** Placeholder boxes in the PDF and warnings like `Converter 'mermaid' is disabled`.

**Fix:** Install optional converters (Docker + `minlag/mermaid-cli`, Draw.io CLI, etc.) or register custom converters in `texsmith.adapters.transformers`. Use `--no-fallback-converters` during debugging to make missing dependencies fail fast.

## Fonts or language mismatches

**Symptom:** `Package polyglossia Error` or `fontspec` warnings after switching languages.

**Fix:** Ensure the `press.language` metadata (front matter or CLI `--language`) maps to a Babel/Polyglossia identifier. Refer to `texsmith --template-info` to confirm defaults and install any necessary language packages (e.g., `tlmgr install babel-french`).

## Still stuck?

1. Re-run with `--debug --classic-output -vv` to capture both TeXSmith diagnostics and raw `latexmk` logs.
2. Attach the failing `.log` plus your template manifest when filing an issue.
3. Mention your TeX distribution and operating system so maintainers can reproduce the environment.
