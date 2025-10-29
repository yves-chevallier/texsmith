"""Utility helpers shared across transformer strategies."""

from __future__ import annotations

from pathlib import Path

from texsmith.core.exceptions import TransformerExecutionError


def points_to_mm(points: float) -> float:
    """Convert PDF points to millimetres."""
    return points * 25.4 / 72


def normalise_pdf_version(pdf_path: Path, *, target_version: str = "1.5") -> None:
    """Re-write a PDF so its header advertises the requested version."""
    try:
        import pypdf  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - optional dependency
        msg = "pypdf is required to normalise PDF artefacts."
        raise TransformerExecutionError(msg) from exc

    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as exc:  # pragma: no cover - defensive
        msg = f"Failed to read generated PDF '{pdf_path}': {exc}"
        raise TransformerExecutionError(msg) from exc

    # Skip rewriting when already on the desired version.
    header = getattr(reader, "pdf_header", b"")
    if isinstance(header, bytes):
        header_text = header.decode("latin-1", "ignore")
        if header_text.startswith("%PDF-"):
            current_version = header_text[5:].strip()
            if current_version == target_version:
                return

    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.pdf_header = f"%PDF-{target_version}\n"

    metadata = reader.metadata or {}
    filtered_metadata = {k: v for k, v in metadata.items() if isinstance(v, str)}
    if filtered_metadata:
        writer.add_metadata(filtered_metadata)

    tmp_path = pdf_path.with_suffix(pdf_path.suffix + ".tmp")
    try:
        with tmp_path.open("wb") as handle:
            writer.write(handle)
    except Exception as exc:  # pragma: no cover - defensive
        msg = f"Failed to rewrite PDF '{pdf_path}' to version {target_version}: {exc}"
        raise TransformerExecutionError(msg) from exc

    tmp_path.replace(pdf_path)


__all__ = ["normalise_pdf_version", "points_to_mm"]
