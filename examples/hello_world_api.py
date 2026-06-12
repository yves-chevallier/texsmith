"""Minimal example: build a PDF with the texsmith Python API.

Generates a Markdown source containing a "Hello World" section, renders it
through the article template, and compiles it to PDF using Tectonic.

Run with: uv run python examples/hello_world_api.py
"""

from __future__ import annotations

from pathlib import Path

from texsmith import ConversionRequest, ConversionService


HERE = Path(__file__).resolve().parent
BUILD_DIR = HERE / "build" / "hello_world_api"
SOURCE = BUILD_DIR / "hello.md"

MARKDOWN = """# Hello World

This is a minimal article generated with the texsmith Python API.

## Greetings

Hello, world!
"""

FRONT_MATTER = {
    "press": {
        "title": "Hello World",
        "authors": [{"name": "Test Author"}],
        "date": "2026-05-19",
    },
}


def main() -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE.write_text(MARKDOWN, encoding="utf-8")

    service = ConversionService()
    request = ConversionRequest(
        documents=[SOURCE],
        front_matter=FRONT_MATTER,
        template="article",
        render_dir=BUILD_DIR,
        embed_fragments=True,
    )

    response = service.execute(request)
    render_result = response.render_result
    print("Main TeX file:", render_result.main_tex_path)

    engine_result = service.build_pdf(render_result, engine="tectonic")
    pdf_path = render_result.main_tex_path.with_suffix(".pdf")
    print("Engine exit status:", engine_result.returncode)
    print("PDF generated at:", pdf_path)
    return pdf_path


if __name__ == "__main__":
    main()
