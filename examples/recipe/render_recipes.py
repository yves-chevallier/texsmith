#!/usr/bin/env python
"""Render recipe collections from YAML manifests using the local recipe template."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from texsmith.api.service import ConversionRequest, ConversionService


logger = logging.getLogger(__name__)


def render(
    recipes: list[Path], *, template: str = "recipe", output_dir: Path | None = None
) -> Path:
    """Render the provided YAML recipes with the dedicated template."""
    service = ConversionService()
    resolved = [path.resolve() for path in recipes]
    build_dir = output_dir.resolve() if output_dir else Path("build/recipes").resolve()
    request = ConversionRequest(
        documents=resolved,
        template=template,
        render_dir=build_dir,
    )
    prepared = service.prepare_documents(request)
    response = service.execute(request, prepared=prepared)
    return response.render_result.main_tex_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipes", nargs="+", type=Path, help="YAML files describing recipes.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("build/recipes"),
        help="Directory where the TeX project will be written.",
    )
    parser.add_argument(
        "-t",
        "--template",
        default="recipe",
        help="Template name or path passed to TeXSmith.",
    )
    args = parser.parse_args()
    tex_path = render(args.recipes, template=args.template, output_dir=args.output_dir)
    logger.info("Wrote %s", tex_path)
