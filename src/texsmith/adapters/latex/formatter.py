"""Utilities for rendering LaTeX partials (snippets)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader, Template
from requests.utils import requote_uri as requote_url

from .pygments import PygmentsLatexHighlighter
from .utils import escape_latex_chars


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.context import DocumentState


TEMPLATE_DIR = Path(__file__).resolve().parent / "partials"


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
        self.legacy_latex_accents: bool = False
        self.env.filters.setdefault("latex_escape", self._escape_latex)
        self.env.filters.setdefault("escape_latex", self._escape_latex)

        template_paths: list[Path] = []
        for ext in (".tex", ".cls"):
            template_paths.extend(template_dir.glob(f"**/*{ext}"))

        self._template_names: dict[str, str] = {}
        for path in template_paths:
            relative = path.relative_to(template_dir)
            key = self._normalise_key(relative.with_suffix("").as_posix())
            self._template_names[key] = relative.as_posix()

        self.templates: dict[str, Template] = {}
        self.default_code_engine = "pygments"
        self.default_code_style = "bw"
        self._pygments: PygmentsLatexHighlighter | None = None

    @staticmethod
    def _normalise_key(name: str) -> str:
        """Normalise template identifiers to align with loader expectations."""
        return name.replace("/", "_")

    @classmethod
    def normalise_key(cls, name: str) -> str:
        """Public wrapper for normalising template identifiers."""
        return cls._normalise_key(name)

    @property
    def template_names(self) -> set[str]:
        """Return the set of available template identifiers."""
        return set(self._template_names)

    def _get_template(self, key: str) -> Template:
        """Return a cached template instance loading it on demand."""
        normalised = self._normalise_key(key)
        template = self.templates.get(normalised)
        if template is not None:
            return template

        template_name = self._template_names.get(normalised)
        if template_name is None:
            raise KeyError(key)

        template = self.env.get_template(template_name)
        self.templates[normalised] = template
        return template

    def __getattr__(self, method: str) -> Callable[..., str]:
        """Proxy calls to templates or custom handlers."""
        mangled = f"handle_{method}"
        try:
            handler = object.__getattribute__(self, mangled)
        except AttributeError:
            handler = None
        if handler is not None:
            return handler  # type: ignore[return-value]

        try:
            template = self._get_template(method)
        except KeyError:
            raise AttributeError(f"Object has no template for '{method}'") from None

        def render_template(*args: Any, **kwargs: Any) -> str:
            """Render the template with optional positional shorthand."""
            if len(args) > 1:
                msg = f"Expected at most 1 argument, got {len(args)}, use keyword arguments instead"
                raise ValueError(msg)
            if args:
                kwargs["text"] = args[0]
            return template.render(**kwargs)

        return render_template

    def __getitem__(self, key: str) -> Callable[..., str]:
        return self._get_template(key).render

    def _escape_url(self, url: str) -> str:
        """Escape a URL for safe use in LaTeX commands."""
        return escape_latex_chars(requote_url(url), legacy_accents=self.legacy_latex_accents)

    def handle_codeinlinett(self, text: str) -> str:
        """Render plain inline code inside \\texttt."""
        escaped = escape_latex_chars(text, legacy_accents=self.legacy_latex_accents)
        escaped = escaped.replace("-", "-\\allowbreak{}")
        return self._get_template("codeinlinett").render(text=escaped)

    def handle_codeblock(
        self,
        code: str,
        language: str = "text",
        filename: str | None = None,
        lineno: bool = False,
        highlight: Iterable[int] | None = None,
        baselinestretch: float | None = None,
        engine: str | None = None,
        state: DocumentState | None = None,
        **_: Any,
    ) -> str:
        """Render code blocks with optional line numbers and highlights."""
        highlight = list(highlight or [])
        optimized_highlight = optimize_list(highlight)
        normalized_engine = (engine or self.default_code_engine or "pygments").lower()
        if normalized_engine not in {"minted", "listings", "verbatim", "pygments"}:
            normalized_engine = "pygments"

        if normalized_engine == "pygments":
            style_name = str(self.default_code_style or "bw").strip() or "bw"
            if self._pygments is None or self._pygments.style != style_name:
                self._pygments = PygmentsLatexHighlighter(style=style_name)
            latex_code, style_defs = self._pygments.render(
                code,
                language,
                linenos=lineno,
                highlight_lines=highlight,
            )
            if state is not None and style_defs:
                state.pygments_styles.setdefault(self._pygments.style_key, style_defs)
            return self._get_template("codeblock_pygments").render(
                code=latex_code,
                language=language,
                linenos=lineno,
                filename=filename,
                baselinestretch=baselinestretch,
                highlight=optimized_highlight,
            )

        if normalized_engine == "listings":
            return self._get_template("codeblock_listings").render(
                code=code,
                language=language,
                linenos=lineno,
                filename=filename,
                baselinestretch=baselinestretch,
                highlight=optimized_highlight,
            )

        if normalized_engine == "verbatim":
            return self._get_template("codeblock_verbatim").render(
                code=code,
                language=language,
                linenos=lineno,
                filename=filename,
                baselinestretch=baselinestretch,
                highlight=optimized_highlight,
            )

        return self._get_template("codeblock").render(
            code=code,
            language=language,
            linenos=lineno,
            filename=filename,
            baselinestretch=baselinestretch,
            highlight=optimized_highlight,
        )

    def url(self, text: str, url: str) -> str:
        """Render a URL, escaping special LaTeX characters."""
        safe_url = self._escape_url(url)
        return self._get_template("url").render(text=text, url=safe_url)

    def handle_href(self, text: str, url: str) -> str:
        """Render \\href links with escaped URLs."""
        return self._get_template("href").render(text=text, url=self._escape_url(url))

    def handle_regex(self, text: str, url: str) -> str:
        """Render regex helper links with escaped URLs."""
        return self._get_template("regex").render(text=text, url=self._escape_url(url))

    def handle_codeinline(
        self,
        *,
        language: str = "text",
        text: str,
        engine: str | None = None,
        state: DocumentState | None = None,
        delimiter: str | None = None,
    ) -> str:
        """Render inline code with engine-specific highlighting."""
        normalized_engine = (engine or self.default_code_engine or "pygments").lower()
        if normalized_engine == "minted":
            delimiter = delimiter or "|"
            return self._get_template("codeinline").render(
                language=language or "text",
                text=text,
                delimiter=delimiter,
            )

        if normalized_engine == "pygments":
            style_name = str(self.default_code_style or "bw").strip() or "bw"
            if self._pygments is None or self._pygments.style != style_name:
                self._pygments = PygmentsLatexHighlighter(style=style_name)
            latex_code, style_defs = self._pygments.render_inline(text, language)
            if state is not None and style_defs:
                state.pygments_styles.setdefault(self._pygments.style_key, style_defs)
            return r"{\ttfamily " + latex_code + "}"

        # listings/verbatim fallback to plain typewriter
        return self.handle_codeinlinett(text)

    def _escape_latex(self, value: str) -> str:
        """Escape helper that honours the formatter legacy accent setting."""
        return escape_latex_chars(value, legacy_accents=self.legacy_latex_accents)

    def svg(self, svg: str | Path) -> str:
        """Render an SVG image by converting it to PDF first."""
        from ..transformers import svg2pdf

        pdfpath = svg2pdf(svg, self.output_path)  # type: ignore[attr-defined]
        return f"\\includegraphics[width=1em]{{{pdfpath}}}"

    def get_cover(self, name: str, **kwargs: Any) -> str:
        """Render a named cover template populated with book metadata."""
        template = self._get_template(f"cover/{name}")
        return template.render(
            title=self.config.title,  # type: ignore[attr-defined]
            author=self.config.author,  # type: ignore[attr-defined]
            subtitle=self.config.subtitle,  # type: ignore[attr-defined]
            email=self.config.email,  # type: ignore[attr-defined]
            year=self.config.year,  # type: ignore[attr-defined]
            **self.config.cover.model_dump(),  # type: ignore[attr-defined]
            **kwargs,
        )

    def override_template(self, name: str, source: str | Path) -> None:
        """Override a built-in template snippet using an external payload."""
        if isinstance(source, Path):
            template_source = source.read_text(encoding="utf-8")
            template_name = source.as_posix()
        else:
            template_source = source
            template_name = name

        template = self.env.from_string(template_source)
        template.name = template_name
        normalised = self._normalise_key(name)
        self.templates[normalised] = template
        self._template_names[normalised] = template_name


__all__ = ["LaTeXFormatter", "optimize_list"]
