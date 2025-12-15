"""HTML utilities for wrapping foreign script runs with data attributes."""

from __future__ import annotations

from collections.abc import Iterable
import unicodedata

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from texsmith.fonts.scripts import ScriptDetector


_DEFAULT_BLOCK_TAGS = {"p"}
_SKIP_TAGS = {"script", "style", "code", "pre"}


def _replace_with_nodes(
    target: NavigableString, replacements: list[object], soup: BeautifulSoup
) -> None:
    if not replacements:
        target.extract()
        return

    def _coerce(value: object) -> NavigableString | Tag:
        if isinstance(value, (NavigableString, Tag)):
            return value
        return soup.new_string(str(value))

    nodes = [_coerce(entry) for entry in replacements]
    first = nodes[0]
    target.replace_with(first)
    cursor = first
    for node in nodes[1:]:
        cursor.insert_after(node)
        cursor = node


def _iter_text(node: Tag, *, skip_names: set[str]) -> str:
    parts: list[str] = []
    for descendant in node.descendants:
        if isinstance(descendant, Comment):
            continue
        if isinstance(descendant, NavigableString):
            if any(
                getattr(parent, "name", "").lower() in skip_names
                for parent in getattr(descendant, "parents", [])
            ):
                continue
            parts.append(str(descendant))
    return "".join(parts)


def _promote_block_script(
    tag: Tag,
    detector: ScriptDetector,
    *,
    soup: BeautifulSoup,  # noqa: ARG001
    segments: list[tuple[str | None, str, object]],
) -> None:
    groups = {group for group, _, _ in segments if group}
    if len(groups) != 1:
        return

    group = groups.pop()
    slug = detector._record_spec(group, None).slug  # noqa: SLF001
    tag.attrs.setdefault("data-script", slug)

    for span in list(tag.find_all("span", attrs={"data-script": slug})):
        span.unwrap()


def wrap_scripts_in_html(
    html: str,
    *,
    block_tags: Iterable[str] | None = None,
    include_whitespace: bool = True,
) -> tuple[str, list[dict[str, str | None]], list[dict[str, object]]]:
    """Annotate script runs in ``html`` and return the transformed payload."""
    soup = BeautifulSoup(html, "html.parser")
    detector = ScriptDetector()

    skip_names = {name.lower() for name in _SKIP_TAGS}
    block_names = {name.lower() for name in (block_tags or _DEFAULT_BLOCK_TAGS)}

    def _is_punctuation(chunk: str) -> bool:
        if not chunk:
            return False
        has_non_ascii = any(ord(char) > 127 for char in chunk if not char.isspace())
        return has_non_ascii and all(
            char.isspace() or unicodedata.category(char).startswith("P") for char in chunk
        )

    def _resolve_segments(
        segments: list[tuple[str | None, str, object]],
    ) -> list[tuple[str | None, str, object]]:
        resolved: list[tuple[str | None, str, object]] = []
        last_group: str | None = None
        last_entry = None
        for group, chunk, entry in segments:
            if not chunk:
                continue
            resolved_group = group
            resolved_entry = entry
            if _is_punctuation(chunk) and (
                (resolved_group is None and last_group is not None)
                or (resolved_group != last_group and last_group is not None)
            ):
                resolved_group = last_group
                resolved_entry = last_entry
            resolved.append((resolved_group, chunk, resolved_entry))
            if resolved_group:
                last_group = resolved_group
                last_entry = resolved_entry or entry
        return resolved

    def _walk(node: Tag) -> None:
        for child in list(node.children):
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                segments = _resolve_segments(
                    detector._segment_text(  # noqa: SLF001
                        str(child), include_whitespace=include_whitespace
                    )
                )
                if not segments or all(group is None for group, _, _ in segments):
                    continue

                replacements: list[object] = []
                for group, chunk, entry in segments:
                    if group:
                        spec = detector._record_spec(group, entry)  # noqa: SLF001
                        spec.count += len(chunk)
                        span = soup.new_tag("span")
                        span.attrs["data-script"] = spec.slug
                        span.append(chunk)
                        replacements.append(span)
                    else:
                        replacements.append(chunk)
                _replace_with_nodes(child, replacements, soup)
                continue

            if isinstance(child, Tag):
                name = (child.name or "").lower()
                if name in skip_names:
                    continue
                _walk(child)

    _walk(soup)

    for tag_name in block_names:
        for tag in soup.find_all(tag_name):
            raw_text = _iter_text(tag, skip_names=skip_names)
            segments = _resolve_segments(
                detector._segment_text(raw_text, include_whitespace=include_whitespace)  # noqa: SLF001
            )
            _promote_block_script(tag, detector, soup=soup, segments=segments)

    usage = [spec.to_mapping() for spec in detector._specs.values()]  # noqa: SLF001
    try:
        summary = detector._ensure_lookup().summary(soup.get_text())  # noqa: SLF001
    except Exception:
        summary = []
    return str(soup), usage, summary


__all__ = ["wrap_scripts_in_html"]
