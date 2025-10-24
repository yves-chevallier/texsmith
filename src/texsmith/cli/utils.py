"""Auxiliary helpers used by CLI commands."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from ..conversion import (
    DOCUMENT_SELECTOR_SENTINEL,
    ConversionCallbacks,
    ConversionError,
    InputKind,
    UnsupportedInputError,
    build_document_context,
    extract_content,
)
from ..markdown import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    MarkdownConversionError,
    render_markdown,
)


if TYPE_CHECKING:
    from ..conversion_contexts import DocumentContext


@dataclass(slots=True)
class SlotAssignment:
    """Mapping of a template slot to a document slice."""

    slot: str
    selector: str | None
    full_document: bool = False


def resolve_option(value: object) -> object:
    if isinstance(value, typer.models.OptionInfo):
        return value.default
    if hasattr(typer.models, "ArgumentInfo") and isinstance(  # type: ignore[attr-defined]
        value, typer.models.ArgumentInfo
    ):
        default = value.default  # type: ignore[attr-defined]
        if default is Ellipsis:
            return []
        return default
    return value


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


def deduplicate_paths(values: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in values:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def split_document_inputs(
    inputs: Iterable[Path],
    extra_bibliography: Iterable[Path],
) -> tuple[list[Path], list[Path]]:
    inline_bibliography: list[Path] = []
    documents: list[Path] = []

    for candidate in inputs:
        suffix = candidate.suffix.lower()
        if suffix in {".bib", ".bibtex"}:
            inline_bibliography.append(candidate)
            continue
        documents.append(candidate)

    combined_bibliography = deduplicate_paths([*inline_bibliography, *extra_bibliography])
    return documents, combined_bibliography


def classify_input_source(path: Path) -> InputKind:
    """Determine the document kind based on its filename suffix."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return InputKind.MARKDOWN
    if suffix in {".html", ".htm"}:
        return InputKind.HTML
    if suffix in {".yaml", ".yml"}:
        raise UnsupportedInputError(
            "MkDocs configuration files are not supported as input. "
            "Provide a Markdown source or an HTML document."
        )
    raise UnsupportedInputError(
        f"Unsupported input file type '{suffix or '<none>'}'. "
        "Provide a Markdown source (.md) or HTML document (.html)."
    )


def prepare_document_context(
    *,
    document_path: Path,
    kind: InputKind,
    selector: str,
    full_document: bool,
    base_level: int,
    heading_level: int,
    drop_title: bool,
    numbered: bool,
    markdown_extensions: list[str],
    callbacks: ConversionCallbacks,
    emit_error_callback: Any,
) -> DocumentContext:
    try:
        raw_payload = document_path.read_text(encoding="utf-8")
    except OSError as exc:
        message = f"Failed to read input document: {exc}"
        if callbacks.emit_error is not None:
            callbacks.emit_error(message, exc)
        else:
            emit_error_callback(message, exception=exc)
        raise ConversionError(message) from exc

    front_matter: dict[str, Any] = {}
    html_payload = raw_payload

    if kind is InputKind.MARKDOWN:
        extensions = markdown_extensions or list(DEFAULT_MARKDOWN_EXTENSIONS)
        try:
            converted = render_markdown(raw_payload, extensions)
        except MarkdownConversionError as exc:
            message = f"Failed to convert Markdown source: {exc}"
            if callbacks.emit_error is not None:
                callbacks.emit_error(message, exc)
            else:
                emit_error_callback(message, exception=exc)
            raise ConversionError(message) from exc
        html_payload = converted.html
        front_matter = converted.front_matter
    else:
        if not full_document:
            try:
                html_payload = extract_content(html_payload, selector)
            except ValueError:
                html_payload = raw_payload

    return build_document_context(
        name=document_path.stem,
        source_path=document_path,
        html=html_payload,
        front_matter=front_matter,
        base_level=base_level,
        heading_level=heading_level,
        drop_title=drop_title,
        numbered=numbered,
    )


def build_unique_stem_map(documents: Iterable[Path]) -> dict[Path, str]:
    used: set[str] = set()
    counters: dict[str, int] = {}
    mapping: dict[Path, str] = {}

    for path in documents:
        base = path.stem
        index = counters.get(base, 0)
        candidate = base if index == 0 else f"{base}-{index + 1}"
        while candidate in used:
            index += 1
            candidate = f"{base}-{index + 1}"
        counters[base] = index + 1
        used.add(candidate)
        mapping[path] = candidate

    return mapping


def determine_output_target(
    template_selected: bool,
    documents: list[Path],
    output_option: Path | None,
) -> tuple[str, Path | None]:
    if template_selected:
        if output_option is None:
            return "template", Path("build")
        if output_option.exists() and output_option.is_file():
            raise typer.BadParameter("Template output must be a directory.")
        if output_option.suffix:
            raise typer.BadParameter("Template output must be a directory path.")
        return "template", output_option

    if output_option is None:
        return "stdout", None

    if output_option.exists() and output_option.is_dir():
        return "directory", output_option

    if output_option.suffix or len(documents) == 1:
        return "file", output_option

    return "directory", output_option


def write_output_file(target: Path, content: str) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise OSError(f"Failed to write LaTeX output to '{target}': {exc}") from exc


def looks_like_document_path(candidate: str) -> bool:
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
    if selector is None:
        return None
    candidate = selector.strip()
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
        candidate = candidate[1:-1].strip()
    return candidate or None


def parse_cli_slot_tokens(
    values: Iterable[str] | None,
) -> list[tuple[str, str | None, str | None, str]]:
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
        full_document = False
        if selector_clean is None:
            full_document = True
            selector_clean = DOCUMENT_SELECTOR_SENTINEL
        else:
            token_lower = selector_clean.strip().lower()
            if token_lower in {"*", DOCUMENT_SELECTOR_SENTINEL.lower()}:
                full_document = True
                selector_clean = DOCUMENT_SELECTOR_SENTINEL

        assignments[target_doc].append(
            SlotAssignment(slot=slot_name, selector=selector_clean, full_document=full_document)
        )

    return assignments


def organise_slot_overrides(
    values: Iterable[str] | None,
    documents: list[Path],
) -> tuple[dict[Path, dict[str, str]], dict[Path, list[SlotAssignment]]]:
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
