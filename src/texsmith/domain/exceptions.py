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
