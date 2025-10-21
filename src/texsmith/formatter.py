"""Utilities for rendering LaTeX templates."""

from __future__ import annotations

from collections.abc import Iterable
import glob
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader, Template
from requests.utils import requote_uri as requote_url

from .utils import escape_latex_chars


TEMPLATE_DIR = Path(__file__).parent / "templates"


def optimize_list(numbers: Iterable[int]) -> list[str]:
    """Merge consecutive integers into human-readable ranges."""

    values = sorted(numbers)
    if not values:
        return []

    optimized: list[str] = []
    start = end = values[0]

    for num in values[1:]:
        if num == end + 1:
            end = num
        else:
            optimized.append(f"{start}-{end}" if start != end else str(start))
            start = end = num

    optimized.append(f"{start}-{end}" if start != end else str(start))
    return optimized


class LaTeXFormatter:
    """Render LaTeX templates using Jinja2 with custom delimiters."""

    def __init__(self, template_dir: Path = TEMPLATE_DIR) -> None:
        self.env = Environment(
            block_start_string=r"\BLOCK{",
            block_end_string=r"}",
            variable_start_string=r"\VAR{",
            variable_end_string=r"}",
            comment_start_string=r"\COMMENT{",
            comment_end_string=r"}",
            loader=FileSystemLoader(template_dir),
        )
        self.env.filters.setdefault("latex_escape", escape_latex_chars)
        self.env.filters.setdefault("escape_latex", escape_latex_chars)

        template_paths: list[Path] = []
        for ext in (".tex", ".cls"):
            template_paths.extend(
                Path(path)
                for path in glob.glob(f"{template_dir}/**/*{ext}", recursive=True)
            )

        templates = [path.relative_to(template_dir) for path in template_paths]
        self.templates: dict[str, Template] = {
            str(filename.with_suffix("")).replace("/", "_"): self.env.get_template(
                str(filename)
            )
            for filename in templates
        }

    def __getattr__(self, method: str) -> Callable[..., str]:
        """Proxy calls to templates or custom handlers."""

        mangled = f"handle_{method}"
        try:
            handler = object.__getattribute__(self, mangled)
        except AttributeError:
            handler = None
        if handler is not None:
            return handler  # type: ignore[return-value]

        template = self.templates.get(method)
        if template is None:
            raise AttributeError(f"Object has no template for '{method}'") from None

        def render_template(*args: Any, **kwargs: Any) -> str:
            """Render the template with optional positional shorthand."""

            if len(args) > 1:
                msg = (
                    "Expected at most 1 argument, "
                    f"got {len(args)}, use keyword arguments instead"
                )
                raise ValueError(msg)
            if args:
                kwargs["text"] = args[0]
            return template.render(**kwargs)

        return render_template

    def __getitem__(self, key: str) -> Callable[..., str]:
        return self.templates[key].render

    def handle_codeblock(
        self,
        code: str,
        language: str = "text",
        filename: str | None = None,
        lineno: bool = False,
        highlight: Iterable[int] | None = None,
        **_: Any,
    ) -> str:
        """Render code blocks with optional line numbers and highlights."""

        highlight = list(highlight or [])
        return self.templates["codeblock"].render(
            code=code,
            language=language,
            linenos=lineno,
            filename=filename,
            highlight=optimize_list(highlight),
        )

    def url(self, text: str, url: str) -> str:
        """Render a URL, escaping special LaTeX characters."""

        safe_url = escape_latex_chars(requote_url(url))
        return self.templates["url"].render(text=text, url=safe_url)

    def svg(self, svg: str | Path) -> str:
        """Render an SVG image by converting it to PDF first."""

        from .transformers import svg2pdf

        pdfpath = svg2pdf(svg, self.output_path)  # type: ignore[attr-defined]
        return f"\\includegraphics[width=1em]{{{pdfpath}}}"

    def get_cover(self, name: str, **kwargs: Any) -> str:
        template = self.templates[f"cover/{name}"]
        return template.render(
            title=self.config.title,  # type: ignore[attr-defined]
            author=self.config.author,  # type: ignore[attr-defined]
            subtitle=self.config.subtitle,  # type: ignore[attr-defined]
            email=self.config.email,  # type: ignore[attr-defined]
            year=self.config.year,  # type: ignore[attr-defined]
            **self.config.cover.model_dump(),  # type: ignore[attr-defined]
            **kwargs,
        )
