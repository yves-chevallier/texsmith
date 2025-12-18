"""Markdown preprocessor normalising inline citation references."""

from __future__ import annotations

import re

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor


_DOI_PATTERN = r"10\.\d{4,9}/[^\s\]]+"
_TOKEN_RE = re.compile(rf"^(?:{_DOI_PATTERN}|[0-9A-Za-z_:-]+)$")
_PATTERN = re.compile(r"\^\[(?P<keys>[^\]]+)\]")


def _clean_keys(payload: str) -> list[str]:
    candidates = [part.strip() for part in payload.split(",")]
    cleaned = [key for key in candidates if key and _TOKEN_RE.match(key)]
    return cleaned


class _MultiCitationPreprocessor(Preprocessor):
    """Convert ``^[A,B]`` references into ``[^A,B]`` before footnote processing."""

    def run(self, lines: list[str]) -> list[str]:
        return [_PATTERN.sub(self._replace_match, line) for line in lines]

    @staticmethod
    def _replace_match(match: re.Match[str]) -> str:
        cleaned = _clean_keys(match.group("keys"))
        if not cleaned:
            return match.group(0)
        return f"[^{','.join(cleaned)}]"


class MultiCitationExtension(Extension):
    """Register the multi-citation preprocessor before the footnotes extension."""

    def extendMarkdown(self, md: Markdown) -> None:  # type: ignore[override]  # noqa: N802
        md.preprocessors.register(
            _MultiCitationPreprocessor(),
            "texsmith_multi_citations",
            priority=5,
        )


def makeExtension(  # noqa: N802
    **kwargs: object,
) -> MultiCitationExtension:  # pragma: no cover - API hook
    return MultiCitationExtension(**kwargs)


__all__ = ["MultiCitationExtension", "makeExtension"]
