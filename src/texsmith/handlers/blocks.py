"""Block-level handlers for structural HTML elements."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
import warnings

from bs4 import NavigableString, Tag

from ..context import RenderContext
from ..exceptions import AssetMissingError, InvalidNodeError
from ..rules import RenderPhase, renders
from ..transformers import drawio2pdf, fetch_image, image2pdf, svg2pdf
from ..utils import is_valid_url, resolve_asset_path


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
        classes = getattr(current, "get", lambda *_: None)("class") or []
        if isinstance(classes, str):
            class_list = classes.split()
        else:
            class_list = list(classes)
        if any(cls in {"admonition", "exercise"} for cls in class_list):
            return "figure_tcolorbox"
        if getattr(current, "name", None) == "details":
            return "figure_tcolorbox"
        current = getattr(current, "parent", None)
    return context.runtime.get("figure_template", "figure")


@renders("div", phase=RenderPhase.PRE, priority=120, name="tabbed_content", auto_mark=False)
def render_tabbed_content(element: Tag, context: RenderContext) -> None:
    """Unwrap MkDocs tabbed content structures."""
    classes = element.get("class") or []
    if "tabbed-set" not in classes:
        return

    titles: list[str] = []
    if labels := element.find("div", class_="tabbed-labels"):
        for label in labels.find_all("label"):
            titles.append(label.get_text(strip=True))
        labels.extract()
    else:
        fallback_titles = [label.get_text(strip=True) for label in element.find_all("label")]
        if fallback_titles:
            for title in fallback_titles:
                if not title:
                    continue
                formatted = context.formatter.strong(text=title)
                heading = NavigableString(f"{formatted}\\par\n")
                heading.processed = True
                element.insert_before(heading)
        element.unwrap()
        return

    for input_node in element.find_all("input", recursive=False):
        input_node.extract()

    tabbed_content = element.find("div", class_="tabbed-content")
    if tabbed_content is None:
        raise InvalidNodeError("Missing tabbed-content container inside tabbed-set")

    for index, block in enumerate(tabbed_content.find_all("div", class_="tabbed-block")):
        title = titles[index] if index < len(titles) else ""
        heading = NavigableString(f"\n\\textbf{{{title}}}\\par\n")
        block.insert_before(heading)
        block.unwrap()

    tabbed_content.unwrap()
    element.unwrap()


@renders(
    "blockquote",
    phase=RenderPhase.POST,
    priority=20,
    name="blockquotes",
    nestable=False,
)
def render_blockquotes(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "epigraph" in classes:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.blockquote(text)
    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)


@renders(phase=RenderPhase.POST, name="lists", auto_mark=False)
def render_lists(root: Tag, context: RenderContext) -> None:
    """Render ordered and unordered lists."""
    for element in _iter_reversed(root.find_all(["ol", "ul"])):
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

        has_checkbox = any(checkboxes)
        latex: str

        if element.name == "ol":
            latex = context.formatter.ordered_list(items=items)
        else:
            if has_checkbox:
                choices = list(zip((c > 0 for c in checkboxes), items, strict=False))
                latex = context.formatter.choices(items=choices)
            else:
                latex = context.formatter.unordered_list(items=items)

        node = NavigableString(latex)
        node.processed = True
        element.replace_with(node)


@renders(phase=RenderPhase.POST, priority=15, name="description_lists", auto_mark=False)
def render_description_lists(root: Tag, context: RenderContext) -> None:
    """Render <dl> elements."""
    for dl in _iter_reversed(root.find_all("dl")):
        items: list[tuple[str | None, str]] = []
        current_term: str | None = None

        for child in dl.find_all(["dt", "dd"], recursive=False):
            if child.name == "dt":
                current_term = child.get_text(strip=False).strip()
            elif child.name == "dd":
                content = child.get_text(strip=False).strip()
                items.append((current_term, content))

        latex = context.formatter.description_list(items=items)
        node = NavigableString(latex)
        node.processed = True
        dl.replace_with(node)


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
        replacement = NavigableString(latex)
        replacement.processed = True
        node.replace_with(replacement)

    for container in root.find_all("div", class_="footnote"):
        for li in container.find_all("li"):
            footnote_id = _normalise_footnote_id(li.get("id"))
            if not footnote_id:
                raise InvalidNodeError("Footnote item missing identifier")
            footnotes[footnote_id] = li.get_text(strip=False).strip()
        container.decompose()

    if footnotes:
        context.state.footnotes.update(footnotes)

    for sup in root.find_all("sup", id=True):
        footnote_id = _normalise_footnote_id(sup.get("id"))
        payload = footnotes.get(footnote_id)
        if payload is None:
            payload = context.state.footnotes.get(footnote_id)
        if footnote_id and footnote_id in bibliography:
            if payload:
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
        identifier = placeholder.get("data-footnote-id") or placeholder.get_text(strip=True)
        footnote_id = identifier.strip() if identifier else ""
        if not footnote_id:
            placeholder.decompose()
            continue

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
            replacement = NavigableString(footnote_id)
            replacement.processed = True
            placeholder.replace_with(replacement)


@renders("p", phase=RenderPhase.POST, priority=90, name="paragraphs", nestable=False)
def render_paragraphs(element: Tag, context: RenderContext) -> None:
    """Render plain paragraphs."""
    if element.get("class"):
        return

    text = element.get_text(strip=False).strip()
    if not text:
        element.decompose()
        return

    node = NavigableString(f"{text}\n")
    node.processed = True
    element.replace_with(node)


@renders("div", phase=RenderPhase.POST, priority=60, name="multicolumns", nestable=False)
def render_columns(element: Tag, context: RenderContext) -> None:
    classes = element.get("class") or []
    if "two-column-list" in classes:
        columns = 2
    elif "three-column-list" in classes:
        columns = 3
    else:
        return

    text = element.get_text(strip=False)
    latex = context.formatter.multicolumn(text, columns=columns)
    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)


@renders("figure", phase=RenderPhase.POST, priority=30, name="figures", nestable=False)
def render_figures(element: Tag, context: RenderContext) -> None:
    """Render <figure> elements and manage associated assets."""
    classes = element.get("class") or []
    if "mermaid-figure" in classes:
        return

    image = element.find("img")
    if image is None:
        table = element.find("table")
        if table is not None:
            identifier = element.get("id")
            if identifier and not table.get("id"):
                table["id"] = identifier
            figcaption = element.find("figcaption")
            if figcaption is not None and table.find("caption") is None:
                caption = context.document.new_tag("caption")
                caption.string = figcaption.get_text(strip=False)
                table.insert(0, caption)
                figcaption.decompose()
            render_tables(table, context)
            element.unwrap()
            return
        raise InvalidNodeError("Figure missing <img> element")

    src = image.get("src")
    if not src:
        raise InvalidNodeError("Figure image missing 'src' attribute")

    width = image.get("width")
    alt_text = image.get("alt") or None
    if not context.runtime.get("copy_assets", True):
        caption_node = element.find("figcaption")
        caption_text = caption_node.get_text(strip=False).strip() if caption_node else None
        placeholder = caption_text or alt_text or "[figure]"
        node = NavigableString(placeholder)
        node.processed = True
        element.replace_with(node)
        return

    if is_valid_url(src):
        artefact = fetch_image(src, output_dir=context.assets.output_root)
        asset_key = src
    else:
        resolved = _resolve_source_path(context, src)
        if resolved is None:
            raise AssetMissingError(f"Unable to resolve figure asset '{src}'")

        suffix = resolved.suffix.lower()
        if suffix == ".svg":
            artefact = svg2pdf(resolved, output_dir=context.assets.output_root)
        elif suffix == ".drawio":
            artefact = drawio2pdf(resolved, output_dir=context.assets.output_root)
        else:
            artefact = image2pdf(resolved, output_dir=context.assets.output_root)
        asset_key = str(resolved)

    stored_path = context.assets.register(asset_key, artefact)

    caption_text = None
    short_caption = alt_text

    if figcaption := element.find("figcaption"):
        caption_text = figcaption.get_text(strip=False).strip()
        figcaption.decompose()

    if short_caption and caption_text and len(caption_text) > len(short_caption):
        short_caption = None

    label = element.get("id")

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

    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)


def _cell_alignment(cell: Tag) -> str:
    style = cell.get("style", "")
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
        caption = caption_node.get_text(strip=False).strip()
        caption_node.decompose()

    label = element.get("id")

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

    node = NavigableString(latex)
    node.processed = True
    element.replace_with(node)
