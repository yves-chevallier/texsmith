"""Custom exception hierarchy for the LaTeX rendering pipeline."""

from __future__ import annotations


class LatexRenderingError(RuntimeError):
    """Base exception for LaTeX rendering failures."""


class AssetMissingError(LatexRenderingError):
    """Raised when an expected asset cannot be located or generated."""


class TransformerExecutionError(LatexRenderingError):
    """Raised when an external converter fails to execute properly."""


class InvalidNodeError(LatexRenderingError):
    """Raised when a handler receives an unexpected DOM node shape."""


class ConversionError(Exception):
    """Raised when a conversion fails and cannot recover."""


def exception_messages(exc: BaseException) -> list[str]:
    """Return the collected message chain for an exception and its causes."""
    messages: list[str] = []
    visited: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        text = str(current).strip()
        if text:
            first_line = text.splitlines()[0].strip()
            if first_line:
                messages.append(first_line)
        current = current.__cause__ or current.__context__
    return messages


def exception_hint(exc: BaseException) -> str | None:
    """Return the most specific message available for an exception chain."""
    messages = exception_messages(exc)
    return messages[-1] if messages else None


def format_rendering_error(error: LatexRenderingError) -> str:
    """Format a human-readable rendering failure summary."""
    cause = error.__cause__
    if cause is None:
        return str(error)
    return f"LaTeX rendering failed: {cause}"


def format_user_friendly_render_error(error: LatexRenderingError) -> str:
    """Return a concise rendering failure summary suitable for end users."""
    summary = "LaTeX rendering failed"
    hint_source = error.__cause__ or error
    hint = exception_hint(hint_source)
    if hint:
        summary = f"{summary}: {hint}"
    if summary.endswith("."):
        summary = summary.rstrip(".")
    return f"{summary}. Re-run with --debug for technical details."
