# Cached Wikipedia images

This folder contains locally cached copies of Wikipedia images used in the examples.

Why this exists:

- CI (especially Windows) occasionally hits HTTP 429 rate limits when fetching directly from `upload.wikimedia.org`.
- Keeping a local copy makes the examples deterministic and prevents flaky builds.

How it works:

- The Markdown examples still reference HTTP URLs, but we point them to the repo via
  `https://raw.githubusercontent.com/yves-chevallier/texsmith/refs/heads/master/.wiki/...`.
- This preserves the HTTP fetch path in the renderer while avoiding third‑party rate limits.

If you need to add new images:

1. Download the file from Wikipedia (or another source with a compatible license).
2. Place it in this folder using a stable filename.
3. Update the example markdown to reference the raw GitHub URL.
