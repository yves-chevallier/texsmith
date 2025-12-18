"""Block-level handlers for structural HTML elements."""

from __future__ import annotations

from collections.abc import Iterable
import io
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any
import warnings

from bs4.element import NavigableString, Tag
from pybtex.database.input import bibtex
from pybtex.exceptions import PybtexError

from texsmith.adapters.latex.utils import escape_latex_chars
from texsmith.core.context import RenderContext
from texsmith.core.exceptions import AssetMissingError, InvalidNodeError
from texsmith.core.rules import RenderPhase, renders
from texsmith.fonts.scripts import record_script_usage_for_slug, render_moving_text


if TYPE_CHECKING:  # pragma: no cover - typing helpers
    from texsmith.core.bibliography.collection import BibliographyCollection

from ._assets import store_local_image_asset, store_remote_image_asset
from ._helpers import (
    coerce_attribute,
    gather_classes,
    is_valid_url,
    mark_processed,
    resolve_asset_path,
)
from .code import (
    render_code_blocks as _render_code_block,
    render_preformatted_code as _render_preformatted_code,
    render_standalone_code_blocks as _render_standalone_code_block,
)
from .inline import _MATH_PAYLOAD_PATTERN, render_inline_code as _render_inline_code


def _prepare_rich_text_content(container: Tag, context: RenderContext) -> None:
    """Ensure inline and block code inside containers render before flattening."""
    for highlight in list(container.find_all("div")):
        classes = gather_classes(highlight.get("class"))
        if "highlight" in classes or "codehilite" in classes:
            _render_code_block(highlight, context)

    for pre in list(container.find_all("pre")):
        _render_preformatted_code(pre, context)

    for code_element in list(container.find_all("code")):
        _render_standalone_code_block(code_element, context)

    for inline in list(container.find_all("code")):
        if inline.find_parent("pre"):
            continue
        _render_inline_code(inline, context)


def _iter_reversed(nodes: Iterable[Tag]) -> Iterable[Tag]:
    stack = list(nodes)
    while stack:
        yield stack.pop()


def _resolve_source_path(context: RenderContext, src: str) -> Path | None:
    runtime_dir = context.runtime.get("source_dir")
    if runtime_dir is not None:
        candidate = Path(runtime_dir) / src
        if candidate.exists():
            return candidate.resolve()

    document_path = context.runtime.get("document_path")
    if document_path is not None:
        resolved = resolve_asset_path(Path(document_path), src)
        if resolved is not None:
            return resolved

    project_dir = getattr(context.config, "project_dir", None)
    if project_dir:
        candidate = Path(project_dir) / src
        if candidate.exists():
            return candidate.resolve()

    return None


def _figure_template_for(element: Tag, context: RenderContext) -> str:
    current = element
    while current is not None:
        raw_classes = getattr(current, "get", lambda *_: None)("class")
        class_list = gather_classes(raw_classes)
        if any(cls in {"admonition", "exercise"} for cls in class_list):
            return "figure_tcolorbox"
        if getattr(current, "name", None) == "details":
            return "figure_tcolorbox"
        current = getattr(current, "parent", None)
    return context.runtime.get("figure_template", "figure")


def _strip_caption_prefix(node: Tag | None) -> None:
    if node is None:
        return

    for span in list(node.find_all("span")):
        classes = gather_classes(span.get("class"))
        if "caption-prefix" in classes or "figure-prefix" in classes:
            span.decompose()


def _render_script_paragraphs(element: Tag, context: RenderContext) -> bool:
    """Render consecutive data-script paragraphs into grouped environments."""
    slug = coerce_attribute(element.get("data-script"))
    if not slug:
        return False

    paragraphs: list[Tag] = []
    cursor: Tag | None = element
    while cursor is not None and isinstance(cursor, Tag):
        if cursor.name != "p" or coerce_attribute(cursor.get("data-script")) != slug:
            break
        paragraphs.append(cursor)
        cursor = cursor.find_next_sibling(lambda tag: isinstance(tag, Tag))

    if not paragraphs:
        return False

    legacy_accents = getattr(context.config, "legacy_latex_accents", False)
    bodies: list[str] = []
    for para in paragraphs:
        text = para.get_text(strip=False)
        if not text.strip():
            continue
        bodies.append(escape_latex_chars(text, legacy_accents=legacy_accents))

    plain_text = "\n\n".join(p.get_text(strip=False) for p in paragraphs)
    record_script_usage_for_slug(slug, plain_text, context)

    content = "\n\n".join(bodies)
    latex = f"\\begin{{{slug}}}\n{content}\n\\end{{{slug}}}\n\n"
    replacement = mark_processed(NavigableString(latex))
    paragraphs[-1].insert_after(replacement)
    for para in paragraphs:
        para.decompose()
    return True


def _split_citation_keys(identifier: str) -> list[str]:
    """Split a comma-separated string into individual citation keys."""
    if not identifier:
        return []
    if "," not in identifier:
        return [identifier.strip()] if _is_doi_key(identifier) else []
    return [part.strip() for part in identifier.split(",") if part.strip()]


def _is_multiline_footnote(text: str) -> bool:
    """Check whether rendered footnote text spans multiple non-empty lines."""
    lines = [line for line in text.splitlines() if line.strip()]
    return len(lines) > 1


def _is_bibliography_placeholder(text: str) -> bool:
    """Return True when a footnote just points readers to the bibliography."""
    normalised = text.strip().rstrip(".").strip().lower()
    return normalised in {"see bibliography", "see the bibliography"}


_DOI_KEY_PATTERN = r"10\.\d{4,9}/[^\s,\]]+"
_CITATION_KEY_PATTERN = rf"(?:{_DOI_KEY_PATTERN}|[A-Za-z0-9_\-:]+)"
_DOI_KEY_RE = re.compile(rf"^{_DOI_KEY_PATTERN}$")
_DEFAULT_DOI_SOURCE = Path("inline-doi-citations.bib")


def _is_doi_key(candidate: str) -> bool:
    """Return True when a citation key matches a DOI shape."""
    return bool(_DOI_KEY_RE.match(candidate.strip()))


def _emit_bibliography_warning(context: RenderContext, message: str) -> None:
    emitter = context.runtime.get("emitter")
    if emitter is not None:
        emitter.warning(message)
        return
    warnings.warn(message, stacklevel=2)


def _inline_doi_source_path(context: RenderContext) -> Path:
    """Return a synthetic source path for inline DOI citations."""
    document_path = context.runtime.get("document_path")
    if isinstance(document_path, Path):
        return Path(f"inline-doi-{document_path.stem}.bib")
    try:
        return Path(f"inline-doi-{Path(str(document_path)).stem}.bib")
    except Exception:
        return _DEFAULT_DOI_SOURCE


def _ensure_bibliography_runtime(
    context: RenderContext,
) -> tuple[dict[str, dict[str, object]], BibliographyCollection]:
    from texsmith.core.bibliography.collection import BibliographyCollection

    runtime_bibliography = context.runtime.get("bibliography")
    if not isinstance(runtime_bibliography, dict):
        runtime_bibliography = {}
        context.runtime["bibliography"] = runtime_bibliography

    collection = context.runtime.get("bibliography_collection")
    if not isinstance(collection, BibliographyCollection):
        collection = BibliographyCollection()
        context.runtime["bibliography_collection"] = collection

    return runtime_bibliography, collection


def _resolve_doi_fetcher(context: RenderContext) -> Any:
    from texsmith.core.bibliography.doi import DoiBibliographyFetcher

    fetcher = context.runtime.get("doi_fetcher")
    if fetcher is not None:
        return fetcher

    fetcher = DoiBibliographyFetcher()
    context.runtime["doi_fetcher"] = fetcher
    return fetcher


def _materialise_doi_entry(key: str, context: RenderContext) -> dict[str, object] | None:
    """Fetch and register a bibliography entry for a DOI citation."""
    from texsmith.core.bibliography.doi import DoiLookupError

    bibliography = context.state.bibliography
    runtime_bibliography, collection = _ensure_bibliography_runtime(context)

    fetcher = _resolve_doi_fetcher(context)
    fetch = getattr(fetcher, "fetch", None)
    if not callable(fetch):
        raise DoiLookupError("Configured DOI fetcher is missing a 'fetch' method.")

    try:
        payload = fetch(key)
    except DoiLookupError as exc:
        _emit_bibliography_warning(context, f"Failed to resolve DOI '{key}': {exc}")
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        _emit_bibliography_warning(context, f"Failed to resolve DOI '{key}': {exc}")
        return None

    parser = bibtex.Parser()
    try:
        parsed = parser.parse_stream(io.StringIO(payload))
    except (OSError, PybtexError) as exc:
        _emit_bibliography_warning(context, f"Failed to parse bibliography entry '{key}': {exc}")
        return None
    if not parsed.entries:
        _emit_bibliography_warning(context, f"Bibliography entry for DOI '{key}' is empty.")
        return None
    if len(parsed.entries) > 1:
        _emit_bibliography_warning(
            context,
            f"Bibliography entry for DOI '{key}' contains multiple records; using the first.",
        )
    resolved_key, _entry_obj = next(iter(parsed.entries.items()))

    source = _inline_doi_source_path(context)
    collection.load_data(parsed, source=source)
    entry = collection.find(resolved_key)
    if entry is None:
        return None

    bibliography[resolved_key] = entry
    runtime_bibliography[resolved_key] = entry
    doi_map: dict[str, str] = context.runtime.setdefault("doi_citation_keys", {})
    doi_map[key] = resolved_key
    return entry


def _ensure_doi_entries(keys: list[str], context: RenderContext) -> None:
    """Materialise bibliography entries for any DOI keys not yet loaded."""
    doi_map: dict[str, str] = context.runtime.setdefault("doi_citation_keys", {})
    for key in list(keys):
        if key in context.state.bibliography:
            continue
        if not _is_doi_key(key):
            continue
        if key in doi_map:
            continue
        resolved = _materialise_doi_entry(key, context)
        if resolved is None:
            continue
        resolved_key = doi_map.get(key)
        if resolved_key:
            # replace original DOI key in-place for downstream handling
            try:
                index = keys.index(key)
                keys[index] = resolved_key
            except ValueError:
                continue


@renders("div", phase=RenderPhase.PRE, priority=120, name="tabbed_content", auto_mark=False)
def render_tabbed_content(element: Tag, context: RenderContext) -> None:
    """Unwrap MkDocs tabbed content structures."""
    classes = gather_classes(element.get("class"))
    if "tabbed-set" not in classes:
        return

    titles: list[str] = []
    if labels := element.find("div", class_="tabbed-labels"):
        for label in labels.find_all("label"):
            titles.append(label.get_text(strip=True))
        labels.extract()
    else:
        fallback_labels = element.find_all("label", recursive=False)
        for label in fallback_labels:
            titles.append(label.get_text(strip=True))
            label.extract()

    for input_node in element.find_all("input", recursive=False):
        input_node.extract()

    content_containers = element.find_all("div", class_="tabbed-content", recursive=False)
    if not content_containers:
        candidate = element.find("div", class_="tabbed-content")
        if candidate is None:
            raise InvalidNodeError("Missing tabbed-content container inside tabbed-set")
        content_containers = [candidate]

    blocks: list[Tag] = []
    for container in content_containers:
        inner_blocks = container.find_all("div", class_="tabbed-block", recursive=False)
        if inner_blocks:
            blocks.extend(inner_blocks)
        else:
            blocks.append(container)

    soup = element.soup

    for index, block in enumerate(blocks):
        title = titles[index] if index < len(titles) else ""
        if soup is None:
            heading = mark_processed(NavigableString(f"\\textbf{{{title}}}\\par\n"))
        else:
            heading = soup.new_tag("p")
            strong = soup.new_tag("strong")
            strong.string = title
            heading.append(strong)
        block.insert_before(heading)

        for highlight in block.find_all("div"):
            highlight_classes = gather_classes(highlight.get("class"))
            if "highlight" not in highlight_classes:
                continue
            if context.is_processed(highlight):
                continue
            parent_before = highlight.parent
            _render_code_block(highlight, context)
            if highlight.parent is not None and highlight.parent is parent_before:
                code_element = highlight.find("code")
                code_text = (
                    code_element.get_text(strip=False)
                    if code_element is not None
                    else highlight.get_text(strip=False)
                )
                if code_text and not code_text.endswith("\n"):
                    code_text += "\n"
                fallback = mark_processed(
                    NavigableString(
                        context.formatter.codeblock(
                            code=code_text,
                            language="text",
                            lineno=False,
                            filename=None,
                            highlight=[],
                            baselinestretch=None,
                        )
                    )
                )
                highlight.replace_with(fallback)
            context.mark_processed(highlight)


@renders(
    "div",
    phase=RenderPhase.PRE,
    priority=130,
    name="tabbed_cleanup",
    auto_mark=False,
    after_children=True,
)
def cleanup_tabbed_content(element: Tag, _context: RenderContext) -> None:
    """Remove tabbed container wrappers after children are processed."""
    classes = gather_classes(element.get("class"))
    if "tabbed-set" not in classes:
        return

    containers = element.find_all("div", class_="tabbed-content", recursive=False)
    if not containers:
        containers = element.find_all("div", class_="tabbed-content")
    if not containers:
        element.unwrap()
        return

    for container in containers:
        inner_blocks = container.find_all("div", class_="tabbed-block", recursive=False)
        if inner_blocks:
            for block in inner_blocks:
                block.unwrap()
        container.unwrap()
    element.unwrap()


@renders(
    "blockquote",
    phase=RenderPhase.POST,
    priority=200,
    name="blockquotes",
    nestable=False,
    after_children=True,
)
def render_blockquotes(element: Tag, context: RenderContext) -> None:
    """Convert blockquote elements into LaTeX blockquote environments."""
    classes = element.get("class") or []
    if "epigraph" in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.blockquote(text)
    element.replace_with(mark_processed(NavigableString(latex)))


@renders(phase=RenderPhase.POST, name="lists", auto_mark=False)
def render_lists(root: Tag, context: RenderContext) -> None:
    """Render ordered and unordered lists."""
    for element in _iter_reversed(root.find_all(["ol", "ul"])):
        _prepare_rich_text_content(element, context)
        items: list[str] = []
        checkboxes: list[int] = []

        for li in element.find_all("li", recursive=False):
            checkbox_input = li.find("input", attrs={"type": "checkbox"})
            if checkbox_input is not None:
                is_checked = checkbox_input.has_attr("checked")
                checkboxes.append(1 if is_checked else -1)
                checkbox_input.extract()
                text = li.get_text(strip=False).strip()
            else:
                text = li.get_text(strip=False).strip()
                if text.startswith("[ ]"):
                    checkboxes.append(-1)
                    text = text[3:].strip()
                elif text.startswith("[x]") or text.startswith("[X]"):
                    checkboxes.append(1)
                    text = text[3:].strip()
                else:
                    checkboxes.append(0)
            items.append(text)

        has_checkbox = any(checkboxes) or bool(gather_classes(element.get("class")))
        latex: str

        if element.name == "ol":
            latex = context.formatter.ordered_list(items=items)
        else:
            if has_checkbox:
                choices = list(zip((c > 0 for c in checkboxes), items, strict=False))
                latex = context.formatter.choices(items=choices)
            else:
                latex = context.formatter.unordered_list(items=items)

        element.replace_with(mark_processed(NavigableString(latex)))


@renders(phase=RenderPhase.POST, priority=15, name="description_lists", auto_mark=False)
def render_description_lists(root: Tag, context: RenderContext) -> None:
    """Render <dl> elements."""
    for dl in _iter_reversed(root.find_all("dl")):
        _prepare_rich_text_content(dl, context)
        items: list[tuple[str | None, str]] = []
        current_term: str | None = None

        for child in dl.find_all(["dt", "dd"], recursive=False):
            if child.name == "dt":
                term = child.get_text(strip=False).strip()
                current_term = term or None
            elif child.name == "dd":
                content = child.get_text(strip=False).strip()
                if not content and current_term is None:
                    continue
                items.append((current_term, content))

        if not items:
            warnings.warn("Discarding empty description list.", stacklevel=2)
            dl.decompose()
            continue

        latex = context.formatter.description_list(items=items)
        dl.replace_with(mark_processed(NavigableString(latex)))


@renders(phase=RenderPhase.POST, priority=5, name="fallback_highlight_blocks", auto_mark=False)
def render_remaining_code_blocks(root: Tag, context: RenderContext) -> None:
    """Convert any remaining MkDocs highlight blocks that escaped earlier passes."""
    for highlight in _iter_reversed(root.find_all("div", class_="highlight")):
        if context.is_processed(highlight):
            continue
        _render_code_block(highlight, context)


@renders(phase=RenderPhase.POST, priority=-10, name="footnotes", auto_mark=False)
def render_footnotes(root: Tag, context: RenderContext) -> None:
    """Extract and render footnote references."""
    footnotes: dict[str, str] = {}
    bibliography = context.state.bibliography

    def _normalise_footnote_id(value: str | None) -> str:
        if not value:
            return ""
        text = str(value).strip()
        if ":" in text:
            prefix, suffix = text.split(":", 1)
            if prefix.startswith("fnref") or prefix.startswith("fn"):
                return suffix
        return text or ""

    def _replace_with_latex(node: Tag, latex: str) -> None:
        replacement = mark_processed(NavigableString(latex))
        node.replace_with(replacement)

    _citation_payload_pattern = re.compile(
        rf"^\s*({_CITATION_KEY_PATTERN}(?:\s*,\s*{_CITATION_KEY_PATTERN})*)\s*$"
    )

    def _citation_keys_from_payload(text: str | None) -> list[str]:
        if not text:
            return []
        match = _citation_payload_pattern.match(text)
        if not match:
            return []
        keys = [part.strip() for part in match.group(1).split(",")]
        return [key for key in keys if key]

    def _render_citation(node: Tag, keys: list[str]) -> bool:
        if not keys:
            return False
        _ensure_doi_entries(keys, context)
        missing = [key for key in keys if key not in bibliography]
        if missing:
            return False
        for key in keys:
            context.state.record_citation(key)
        latex = context.formatter.citation(key=",".join(keys))
        _replace_with_latex(node, latex)
        return True

    citation_footnotes: dict[str, list[str]] = {}
    invalid_footnotes: set[str] = set()

    for container in root.find_all("div", class_="footnote"):
        for li in container.find_all("li"):
            footnote_id = _normalise_footnote_id(coerce_attribute(li.get("id")))
            if not footnote_id:
                raise InvalidNodeError("Footnote item missing identifier")
            text = li.get_text(strip=False)
            if _is_multiline_footnote(text):
                warnings.warn(
                    f"Footnote '{footnote_id}' spans multiple lines and cannot be rendered; dropping it.",
                    stacklevel=2,
                )
                invalid_footnotes.add(footnote_id)
                continue
            text = text.strip()
            footnotes[footnote_id] = text
            recovered = _citation_keys_from_payload(text)
            if recovered:
                citation_footnotes[footnote_id] = recovered
        container.decompose()

    if footnotes:
        context.state.footnotes.update(footnotes)

    for sup in root.find_all("sup", id=True):
        footnote_id = _normalise_footnote_id(coerce_attribute(sup.get("id")))
        if footnote_id in invalid_footnotes:
            sup.decompose()
            continue
        citation_keys = citation_footnotes.get(footnote_id)
        if citation_keys and _render_citation(sup, citation_keys):
            continue
        payload = footnotes.get(footnote_id)
        if payload is None:
            payload = context.state.footnotes.get(footnote_id)
        if payload is None:
            citation_keys = _split_citation_keys(footnote_id)
            if citation_keys and _render_citation(sup, citation_keys):
                continue
            # Fall back to default handling/warnings for unresolved citations.
        if footnote_id and footnote_id in bibliography:
            placeholder_note = bool(payload) and _is_bibliography_placeholder(payload)
            if payload and not placeholder_note:
                warnings.warn(
                    f"Conflicting bibliography definition for '{footnote_id}'.",
                    stacklevel=2,
                )
            context.state.record_citation(footnote_id)
            latex = context.formatter.citation(key=footnote_id)
            _replace_with_latex(sup, latex)
            continue

        if payload is None:
            if footnote_id and footnote_id not in bibliography:
                warnings.warn(
                    f"Reference to '{footnote_id}' is not in your bibliography...",
                    stacklevel=2,
                )
            continue

        latex = context.formatter.footnote(payload)
        _replace_with_latex(sup, latex)

    for placeholder in root.find_all("texsmith-missing-footnote"):
        identifier_attr = coerce_attribute(placeholder.get("data-footnote-id"))
        identifier = identifier_attr or placeholder.get_text(strip=True)
        footnote_id = identifier.strip() if identifier else ""
        if not footnote_id:
            placeholder.decompose()
            continue
        if footnote_id in invalid_footnotes:
            placeholder.decompose()
            continue

        citation_keys = citation_footnotes.get(footnote_id)
        if citation_keys and _render_citation(placeholder, citation_keys):
            continue

        citation_keys = _split_citation_keys(footnote_id)
        if citation_keys and _render_citation(placeholder, citation_keys):
            continue
        # Fall back to default handling for unresolved citations.

        if footnote_id in bibliography:
            context.state.record_citation(footnote_id)
            latex = context.formatter.citation(key=footnote_id)
            _replace_with_latex(placeholder, latex)
        else:
            payload = context.state.footnotes.get(footnote_id)
            if payload:
                latex = context.formatter.footnote(payload)
                _replace_with_latex(placeholder, latex)
                continue
            warnings.warn(
                f"Reference to '{footnote_id}' is not in your bibliography...",
                stacklevel=2,
            )
            replacement = mark_processed(NavigableString(footnote_id))
            placeholder.replace_with(replacement)


@renders(
    "p",
    "span",
    phase=RenderPhase.POST,
    priority=100,
    name="latex_raw",
    nestable=False,
)
def render_latex_raw(element: Tag, _context: RenderContext) -> None:
    """Preserve raw LaTeX payloads embedded in hidden paragraphs."""
    classes = gather_classes(element.get("class"))
    if "latex-raw" not in classes:
        return

    text = element.get_text(strip=False)
    replacement = mark_processed(NavigableString(text))
    element.replace_with(replacement)


@renders("p", phase=RenderPhase.POST, priority=90, name="paragraphs", nestable=False)
def render_paragraphs(element: Tag, context: RenderContext) -> None:
    """Render plain paragraphs with script-aware wrapping."""
    if _render_script_paragraphs(element, context):
        return
    if element.get("data-texsmith-latex") == "true":
        content = element.get_text(strip=False)
        element.replace_with(mark_processed(NavigableString(f"{content}\n")))
        return
    if element.get("class"):
        return

    raw_text = element.get_text(strip=False).strip("\n")
    if not raw_text.strip():
        element.decompose()
        return

    legacy_accents = getattr(context.config, "legacy_latex_accents", False)
    contains_math = bool(_MATH_PAYLOAD_PATTERN.search(raw_text))
    escape_text = "\\" not in raw_text and not contains_math
    rendered = render_moving_text(
        raw_text,
        context,
        legacy_accents=legacy_accents,
        include_whitespace=True,
        wrap_scripts=escape_text,
        escape=escape_text,
    )
    element.replace_with(mark_processed(NavigableString(f"{rendered}\n")))


@renders("div", phase=RenderPhase.POST, priority=60, name="multicolumns", nestable=False)
def render_columns(element: Tag, context: RenderContext) -> None:
    """Render lists specially marked as multi-column blocks."""
    classes = gather_classes(element.get("class"))
    if "two-column-list" in classes:
        columns = 2
    elif "three-column-list" in classes:
        columns = 3
    else:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.multicolumn(text, columns=columns)
    element.replace_with(mark_processed(NavigableString(latex)))


@renders("figure", phase=RenderPhase.POST, priority=30, name="figures", nestable=False)
def render_figures(element: Tag, context: RenderContext) -> None:
    """Render <figure> elements and manage associated assets."""
    classes = gather_classes(element.get("class"))
    if "mermaid-figure" in classes:
        return

    image = element.find("img")
    if image is None:
        table = element.find("table")
        if table is not None:
            identifier = coerce_attribute(element.get("id"))
            if identifier and not table.get("id"):
                table["id"] = identifier
            figcaption = element.find("figcaption")
            if figcaption is not None and table.find("caption") is None:
                caption = context.document.new_tag("caption")
                _strip_caption_prefix(figcaption)
                caption.string = figcaption.get_text(strip=False)
                table.insert(0, caption)
                figcaption.decompose()
            render_tables(table, context)
            element.unwrap()
            return
        raise InvalidNodeError("Figure missing <img> element")

    src = coerce_attribute(image.get("src"))
    if not src:
        raise InvalidNodeError("Figure image missing 'src' attribute")

    width = coerce_attribute(image.get("width")) or None
    alt_text = coerce_attribute(image.get("alt")) or None
    if not context.runtime.get("copy_assets", True):
        caption_node = element.find("figcaption")
        caption_text = caption_node.get_text(strip=False).strip() if caption_node else None
        placeholder = caption_text or alt_text or "[figure]"
        element.replace_with(mark_processed(NavigableString(placeholder)))
        return

    if is_valid_url(src):
        stored_path = store_remote_image_asset(context, src)
    else:
        resolved = _resolve_source_path(context, src)
        if resolved is None:
            raise AssetMissingError(f"Unable to resolve figure asset '{src}'")

        stored_path = store_local_image_asset(context, resolved)

    caption_text = None
    short_caption = alt_text

    if figcaption := element.find("figcaption"):
        _strip_caption_prefix(figcaption)
        caption_text = figcaption.get_text(strip=False).strip()
        figcaption.decompose()

    if short_caption and caption_text and len(caption_text) > len(short_caption):
        short_caption = None

    label = coerce_attribute(element.get("id"))

    template_name = _figure_template_for(element, context)
    formatter = getattr(context.formatter, template_name)
    asset_path = context.assets.latex_path(stored_path)
    latex = formatter(
        path=asset_path,
        caption=caption_text or short_caption,
        shortcaption=short_caption,
        label=label,
        width=width,
    )

    element.replace_with(mark_processed(NavigableString(latex)))


def _cell_alignment(cell: Tag) -> str:
    style = coerce_attribute(cell.get("style")) or ""
    if "text-align: right" in style:
        return "right"
    if "text-align: center" in style:
        return "center"
    return "left"


@renders("table", phase=RenderPhase.POST, priority=40, name="tables", nestable=False)
def render_tables(element: Tag, context: RenderContext) -> None:
    """Render HTML tables to LaTeX."""
    caption = None
    if caption_node := element.find("caption"):
        _strip_caption_prefix(caption_node)
        caption = caption_node.get_text(strip=False).strip()
        caption_node.decompose()

    label = coerce_attribute(element.get("id"))

    table_rows: list[list[str]] = []
    styles: list[list[str]] = []
    is_large = False

    for row in element.find_all("tr"):
        row_values: list[str] = []
        row_styles: list[str] = []
        for cell in row.find_all(["th", "td"]):
            content = cell.get_text(strip=False).strip()
            row_values.append(content)
            row_styles.append(_cell_alignment(cell))
        table_rows.append(row_values)
        styles.append(row_styles)

        stripped = "".join(
            re.sub(r"\\href\{[^\}]+?\}|\\\w{3,}|[\{\}|]", "", col) for col in row_values
        )
        if len(stripped) > 50:
            is_large = True

    columns = styles[0] if styles else []
    latex = context.formatter.table(
        columns=columns,
        rows=table_rows,
        caption=caption,
        label=label,
        is_large=is_large,
    )

    element.replace_with(mark_processed(NavigableString(latex)))
