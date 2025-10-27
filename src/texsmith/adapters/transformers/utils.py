"""Utility helpers shared across transformer strategies."""

from __future__ import annotations


def points_to_mm(points: float) -> float:
    """Convert PDF points to millimetres."""
    return points * 25.4 / 72


__all__ = ["points_to_mm"]
