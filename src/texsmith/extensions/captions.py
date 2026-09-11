"""Caption lines: ``Table: … {#id}``, ``Figure: …`` and ``Listing: …``.

TMark has one caption pattern for every float (spec §Captions and floats):
the paragraph adjacent to a table, an image paragraph or a fenced code block,
spelled ``Kind: text {attrs}``. The canonical position is *after* the block;
a ``Table:`` line before its table is accepted sugar. The attribute list is
optional and may be a full ``attr_list`` payload (``{#fig:x .wide lang=fr}``,
spec challenge C23); the ``#id`` is the float's anchor.

Attachment (spec challenge C7): the line attaches to the float *before* it
when that float is of the matching kind and has no caption yet, otherwise to
the float *after* it. A kind mismatch (``Figure:`` under a table) or a caption
with no float next to it leaves the paragraph alone — a lint, not this
processor, complains about it.

The treeprocessor rewrites the DOM into the shapes the shipping forms already
produce, so the HTML reader and both writers need no new case:

- ``Table:`` becomes a ``<caption>`` child of the ``<table>`` with the id on
  the table — exactly what the before-form has always produced;
- ``Figure:`` and ``Listing:`` wrap the host and the caption in
  ``<figure id="…"><host/><figcaption><p>…</p></figcaption></figure>``, the
  shape ``pymdownx.blocks.caption`` emits, the whole attribute list landing on
  the ``<figure>``.

Fenced code blocks and ``yaml table`` fences never reach the tree as elements:
they are ``htmlStash`` placeholders wrapped in a ``<p>``. A code block is
recognised through the stashed HTML it stands for; a ``yaml table`` is
captioned by the yaml-table preprocessor, which reads the same grammar
through :func:`parse_caption_line`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from xml.etree import ElementTree

from markdown import Markdown, util
from markdown.extensions.attr_list import AttrListTreeprocessor
from markdown.treeprocessors import Treeprocessor


CAPTION_LINE_RE = re.compile(
    r"^(?P<kind>Table|Figure|Listing):\s*(?P<caption>[\s\S]*?)"
    r"(?:\s+\{(?P<attrs>[^}\n]+)\})?\s*$"
)
_KIND_PREFIX_RE = re.compile(r"^\s*(?P<kind>Table|Figure|Listing):")
_ID_ATTR_RE = re.compile(r"#([A-Za-z][\w:.\-]*)")
#: A trailing ``{attrs}`` suffix (with optional surrounding whitespace).
_ATTRS_SUFFIX_RE = re.compile(r"\s*\{([^}\n]+)\}\s*$")
#: Marker the yaml-table extension leaves between a Markdown table and its
#: ``yaml table-config`` fence; the canonical order puts the caption after both.
_TABLE_CONFIG_TAG = "texsmith-table-config"
#: Stashed HTML of a fenced code block (``pymdownx.superfences`` with or
#: without highlighting) — the host a ``Listing:`` line captions.
_CODE_HOST_RE = re.compile(r'^\s*<(?:div class="[^"]*\bhighlight\b[^"]*"|pre\b)')
#: A diagram fence is an image, not a listing (spec: ``mermaid image``).
_DIAGRAM_HOST_RE = re.compile(r'^\s*<(?:div|pre) class="[^"]*\bmermaid\b')


@dataclass(slots=True)
class CaptionLine:
    """A parsed ``Kind: text {attrs}`` line."""

    kind: str
    """``table``, ``figure`` or ``listing``."""
    text: str | None
    """The plain caption text; ``None`` when it carries inline elements."""
    attrs: str | None
    """The attribute-list payload between the braces, if any."""
    label: str | None
    """The ``#id`` of the attribute list, if any."""


def parse_caption_line(line: str) -> CaptionLine | None:
    """Parse a plain-text caption line; ``None`` when it is not one."""
    match = CAPTION_LINE_RE.match(line.strip())
    if match is None:
        return None
    attrs = match.group("attrs")
    return CaptionLine(
        kind=match.group("kind").lower(),
        text=match.group("caption").strip() or None,
        attrs=attrs,
        label=_label_from_attrs(attrs),
    )


def _label_from_attrs(attrs: str | None) -> str | None:
    if not attrs:
        return None
    match = _ID_ATTR_RE.search(attrs)
    return match.group(1) if match else None


class CaptionLineTreeprocessor(Treeprocessor):
    """Attach ``Kind: … {attrs}`` paragraphs to the float next to them."""

    def run(self, root: ElementTree.Element) -> ElementTree.Element | None:  # type: ignore[override]
        for paragraph in list(root.iter("p")):
            line = _caption_from_paragraph(paragraph)
            if line is None:
                continue
            parent = _parent_of(root, paragraph)
            if parent is None:
                continue
            siblings = list(parent)
            index = siblings.index(paragraph)
            # ``or`` would drop a childless host: an ElementTree element with
            # no children is falsy, and a code-block placeholder ``<p>`` has none.
            host = self._host_before(siblings, index, line.kind)
            if host is None:
                host = self._host_after(siblings, index, line.kind)
            if host is None:
                continue
            if line.kind == "table":
                _attach_table_caption(parent, paragraph, host, line)
            else:
                _wrap_in_figure(self.md, parent, paragraph, host, line)
        return None

    def _host_before(
        self, siblings: list[ElementTree.Element], index: int, kind: str
    ) -> ElementTree.Element | None:
        cursor = index - 1
        while cursor >= 0 and siblings[cursor].tag == _TABLE_CONFIG_TAG:
            cursor -= 1
        if cursor < 0:
            return None
        candidate = siblings[cursor]
        return candidate if self._is_host(candidate, kind) else None

    def _host_after(
        self, siblings: list[ElementTree.Element], index: int, kind: str
    ) -> ElementTree.Element | None:
        if index + 1 >= len(siblings):
            return None
        candidate = siblings[index + 1]
        return candidate if self._is_host(candidate, kind) else None

    def _is_host(self, element: ElementTree.Element, kind: str) -> bool:
        """Whether ``element`` is an uncaptioned float of ``kind``."""
        if kind == "table":
            return element.tag == "table" and element.find("caption") is None
        if element.tag != "p":
            return False
        if kind == "figure":
            return _is_image_paragraph(element)
        return self._is_code_block(element)

    def _is_code_block(self, paragraph: ElementTree.Element) -> bool:
        """Whether ``paragraph`` is the placeholder of a stashed code block."""
        if len(paragraph):
            return False
        match = util.HTML_PLACEHOLDER_RE.fullmatch((paragraph.text or "").strip())
        if match is None:
            return False
        try:
            html = self.md.htmlStash.rawHtmlBlocks[int(match.group(1))]
        except (IndexError, ValueError):
            return False
        if not isinstance(html, str):
            return False
        return bool(_CODE_HOST_RE.match(html)) and not _DIAGRAM_HOST_RE.match(html)


def _caption_from_paragraph(paragraph: ElementTree.Element) -> CaptionLine | None:
    text = paragraph.text or ""
    if not len(paragraph):
        return parse_caption_line(text)
    # The paragraph carries inline elements (``<em>``, ``<code>``, …): the
    # optional ``{attrs}`` suffix lives in the tail of the last child.
    head = _KIND_PREFIX_RE.match(text)
    if head is None:
        return None
    match = _ATTRS_SUFFIX_RE.search((paragraph[-1].tail or "").rstrip())
    attrs = match.group(1) if match else None
    return CaptionLine(
        kind=head.group("kind").lower(),
        text=None,
        attrs=attrs,
        label=_label_from_attrs(attrs),
    )


def _is_image_paragraph(paragraph: ElementTree.Element) -> bool:
    """A paragraph made of images only (the spec's figure host)."""
    if not len(paragraph) or (paragraph.text or "").strip():
        return False
    return all(child.tag == "img" and not (child.tail or "").strip() for child in paragraph)


def _parent_of(
    root: ElementTree.Element, element: ElementTree.Element
) -> ElementTree.Element | None:
    for parent in root.iter():
        for child in parent:
            if child is element:
                return parent
    return None


def _strip_caption_markup(paragraph: ElementTree.Element, line: CaptionLine) -> None:
    """Drop the ``Kind:`` prefix and the ``{attrs}`` suffix from ``paragraph``."""
    if not len(paragraph):
        paragraph.text = line.text or ""
        return
    text = (paragraph.text or "").lstrip()
    paragraph.text = text[text.index(":") + 1 :].lstrip()
    if line.attrs is not None:
        last = paragraph[-1]
        last.tail = _ATTRS_SUFFIX_RE.sub("", (last.tail or "").rstrip())


def _attach_table_caption(
    parent: ElementTree.Element,
    paragraph: ElementTree.Element,
    table: ElementTree.Element,
    line: CaptionLine,
) -> None:
    """Move the caption into a ``<caption>`` of ``table``; the id onto the table.

    Both the yaml-table renderer and the legacy table renderer consume
    ``<caption>`` directly, so no wrapper is needed.
    """
    _strip_caption_markup(paragraph, line)
    caption = ElementTree.Element("caption")
    caption.text = paragraph.text
    for child in list(paragraph):
        caption.append(child)
    table.insert(0, caption)
    if line.label and not table.get("id"):
        table.set("id", line.label)

    # Preserve the paragraph's trailing text on whichever neighbour will
    # still be there after removal — otherwise text between the caption
    # and the table is silently lost.
    siblings = list(parent)
    index = siblings.index(paragraph)
    if paragraph.tail:
        if index == 0:
            parent.text = (parent.text or "") + paragraph.tail
        else:
            previous = siblings[index - 1]
            previous.tail = (previous.tail or "") + paragraph.tail
    parent.remove(paragraph)


def _wrap_in_figure(
    md: Markdown,
    parent: ElementTree.Element,
    paragraph: ElementTree.Element,
    host: ElementTree.Element,
    line: CaptionLine,
) -> None:
    """Replace ``host`` and ``paragraph`` with a ``<figure>`` holding both."""
    figure = ElementTree.Element("figure")
    if line.attrs:
        AttrListTreeprocessor(md).assign_attrs(figure, line.attrs)
    if line.label and not figure.get("id"):
        figure.set("id", line.label)

    siblings = list(parent)
    first, second = sorted((host, paragraph), key=siblings.index)
    position = siblings.index(first)
    figure.tail = second.tail
    parent.remove(host)
    parent.remove(paragraph)

    _strip_caption_markup(paragraph, line)
    figure.text = "\n"
    figure.append(host)
    host.tail = "\n"
    figcaption = ElementTree.SubElement(figure, "figcaption")
    figcaption.text = "\n"
    figcaption.tail = "\n"
    figcaption.append(paragraph)
    paragraph.tail = "\n"
    parent.insert(position, figure)


__all__ = ["CAPTION_LINE_RE", "CaptionLine", "CaptionLineTreeprocessor", "parse_caption_line"]
