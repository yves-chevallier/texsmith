"""Auxiliary helpers used by CLI commands."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import typer

from texsmith.api.service import SlotAssignment
from texsmith.core.conversion.inputs import DOCUMENT_SELECTOR_SENTINEL


def parse_slot_option(values: Iterable[str] | None) -> dict[str, str]:
    """Parse CLI slot overrides declared as 'slot:Section' pairs."""
    overrides: dict[str, str] = {}
    if not values:
        return overrides

    for raw in values:
        if not isinstance(raw, str):
            continue
        entry = raw.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(f"Invalid slot override '{raw}', expected format 'slot:Section'.")
        slot_name, selector = entry.split(":", 1)
        slot_name = slot_name.strip()
        selector = selector.strip()
        if not slot_name or not selector:
            raise ValueError(f"Invalid slot override '{raw}', expected format 'slot:Section'.")
        overrides[slot_name] = selector

    return overrides


def determine_output_target(
    template_selected: bool,
    documents: list[Path],
    output_option: Path | None,
) -> tuple[str, Path | None]:
    """Infer where conversion output should be written based on CLI arguments."""
    if template_selected:
        if output_option is None:
            base_dir = documents[0].parent if documents else Path()
            return "template", (base_dir / "build")
        suffix = output_option.suffix.lower()
        if suffix == ".pdf":
            return "template-pdf", output_option
        if output_option.exists() and output_option.is_file():
            raise typer.BadParameter("Template output must be a directory.")
        if suffix:
            raise typer.BadParameter("Template output must be a directory path.")
        return "template", output_option

    if output_option is None:
        return "stdout", None

    if output_option.exists() and output_option.is_dir():
        return "directory", output_option

    if output_option.suffix:
        return "file", output_option

    return "directory", output_option


def write_output_file(target: Path, content: str) -> None:
    """Persist LaTeX content to disk, creating parent directories as needed."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise OSError(f"Failed to write LaTeX output to '{target}': {exc}") from exc


def looks_like_document_path(candidate: str) -> bool:
    """Return True when the string has an extension resembling a document."""
    suffix = Path(candidate).suffix.lower()
    return bool(suffix) and suffix in {
        ".md",
        ".markdown",
        ".mdown",
        ".mkd",
        ".html",
        ".htm",
    }


def normalise_selector(selector: str | None) -> str | None:
    """Strip surrounding quotes and whitespace from user-provided selectors."""
    if selector is None:
        return None
    candidate = selector.strip()
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
        candidate = candidate[1:-1].strip()
    return candidate or None


def parse_cli_slot_tokens(
    values: Iterable[str] | None,
) -> list[tuple[str, str | None, str | None, str]]:
    """Tokenise slot overrides into (slot, path, selector, raw) tuples."""
    tokens: list[tuple[str, str | None, str | None, str]] = []
    if not values:
        return tokens

    for raw in values:
        if not isinstance(raw, str):
            continue
        entry = raw.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise typer.BadParameter(
                f"Invalid slot override '{raw}', expected format "
                f"'slot:selector' or 'slot:file[:selector]'."
            )
        slot_name, remainder = entry.split(":", 1)
        slot_name = slot_name.strip()
        remainder = remainder.strip()
        if not slot_name or not remainder:
            raise typer.BadParameter(
                f"Invalid slot override '{raw}', expected format "
                f"'slot:selector' or 'slot:file[:selector]'."
            )

        path_hint: str | None
        selector_value: str | None
        if ":" in remainder:
            path_part, selector_part = remainder.split(":", 1)
            path_part = path_part.strip()
            selector_value = normalise_selector(selector_part)
            path_hint = path_part or None
        else:
            if looks_like_document_path(remainder):
                path_hint = remainder
                selector_value = None
            else:
                path_hint = None
                selector_value = normalise_selector(remainder)

        tokens.append((slot_name, path_hint, selector_value, raw))

    return tokens


def resolve_slot_assignments(
    tokens: list[tuple[str, str | None, str | None, str]],
    documents: list[Path],
) -> dict[Path, list[SlotAssignment]]:
    """Resolve parsed slot tokens against provided documents."""
    assignments: dict[Path, list[SlotAssignment]] = {doc: [] for doc in documents}
    if not tokens:
        return assignments

    resolved_index = {doc.resolve(): doc for doc in documents}
    name_index: dict[str, list[Path]] = {}
    for doc in documents:
        name_index.setdefault(doc.name, []).append(doc)

    for slot_name, path_hint, selector_value, raw in tokens:
        target_doc: Path | None = None
        if path_hint is None:
            if len(documents) == 1:
                target_doc = documents[0]
            else:
                raise typer.BadParameter(
                    f"slot override '{raw}' requires a document "
                    "path when multiple inputs are provided."
                )
        else:
            candidate_path = Path(path_hint)
            resolved_candidate: Path | None = None
            try:
                base = (
                    candidate_path if candidate_path.is_absolute() else Path.cwd() / candidate_path
                )
                resolved_candidate = base.resolve()
            except OSError:
                resolved_candidate = None

            if resolved_candidate is not None and resolved_candidate in resolved_index:
                target_doc = resolved_index[resolved_candidate]
            else:
                matches = name_index.get(candidate_path.name, [])
                if len(matches) == 1:
                    target_doc = matches[0]
                elif len(matches) > 1:
                    raise typer.BadParameter(
                        f"slot override '{raw}' is ambiguous; multiple "
                        f"documents match '{candidate_path.name}'."
                    )

        if target_doc is None:
            raise typer.BadParameter(f"slot override '{raw}' does not match any provided document.")

        selector_clean = selector_value
        include_document = False
        if selector_clean is None:
            include_document = True
        else:
            token_lower = selector_clean.strip().lower()
            if token_lower in {"*", DOCUMENT_SELECTOR_SENTINEL.lower()}:
                include_document = True
                selector_clean = None

        assignments[target_doc].append(
            SlotAssignment(
                slot=slot_name, selector=selector_clean, include_document=include_document
            )
        )

    return assignments


def organise_slot_overrides(
    values: Iterable[str] | None,
    documents: list[Path],
) -> tuple[dict[Path, dict[str, str]], dict[Path, list[SlotAssignment]]]:
    """Produce slot selector overrides and assignments for downstream processing."""
    tokens = parse_cli_slot_tokens(values)
    assignments = resolve_slot_assignments(tokens, documents)

    slot_overrides: dict[Path, dict[str, str]] = {}
    for doc, entries in assignments.items():
        if not entries:
            continue
        mapping = slot_overrides.setdefault(doc, {})
        for entry in entries:
            if entry.selector is not None:
                mapping[entry.slot] = entry.selector

    return slot_overrides, assignments
