"""Extension to capture undefined Markdown footnotes."""

from __future__ import annotations

from types import MethodType
from typing import Any
import xml.etree.ElementTree as ElementTree

from markdown.extensions import Extension
from markdown.extensions.footnotes import FootnoteExtension


class MissingFootnotesExtension(Extension):
    """Detect footnote references lacking explicit definitions."""

    def __init__(self, **kwargs: Any) -> None:
        self.config = {
            "element": ["texsmith-missing-footnote", "Tag inserted for missing notes."],
            "text_template": [
                "{id}",
                "Fallback text rendered for missing notes (can reference {id}).",
            ],
            "css_class": ["", "CSS class applied to placeholder nodes."],
            "link_to_list": [
                False,
                "When true, link to the generated footnote list despite the absence.",
            ],
            "data_attribute": [
                "data-footnote-id",
                "Custom attribute storing the missing footnote identifier.",
            ],
        }
        super().__init__(**kwargs)
        self._footnotes_ext: FootnoteExtension | None = None
        self._patched_pattern = False
        self.missing_ids: set[str] = set()

    def reset(self) -> None:
        """Reset cached state before each Markdown conversion."""
        self.missing_ids.clear()

    # -- internals ---------------------------------------------------------
    def _get_footnotes_extension(self, md: Any) -> FootnoteExtension | None:
        if self._footnotes_ext is not None:
            return self._footnotes_ext

        for extension in getattr(md, "registeredExtensions", []):
            if isinstance(extension, FootnoteExtension):
                self._footnotes_ext = extension
                break
        return self._footnotes_ext

    def extendMarkdown(self, md: Any) -> None:  # noqa: N802 - markdown hook
        """Patch the inline footnote processor to capture missing notes."""
        md.registerExtension(self)
        if self._patched_pattern:
            return

        pattern = self._resolve_footnote_pattern(md)
        if pattern is None:
            raise RuntimeError(
                "MissingFootnotesExtension requires the 'footnotes' extension to be "
                "registered beforehand."
            )

        original_handle = pattern.handleMatch
        extension = self

        def patched_handle(self_pattern: Any, match: Any, data: Any) -> Any:
            result = original_handle(match, data)
            if result and result[0] is not None:
                return result

            footnote_id = match.group(1)
            extension.missing_ids.add(footnote_id)
            node = extension.build_placeholder(footnote_id, self_pattern)
            return node, match.start(0), match.end(0)

        pattern.handleMatch = MethodType(patched_handle, pattern)
        self._patched_pattern = True

    def _resolve_footnote_pattern(self, md: Any) -> Any:
        patterns = getattr(md.inlinePatterns, "items", None)
        if callable(patterns):
            for name, pattern in md.inlinePatterns.items():
                if name == "footnote":
                    return pattern
        else:
            try:
                return md.inlinePatterns["footnote"]
            except KeyError:
                return None
        return None

    def build_placeholder(self, identifier: str, pattern: Any) -> ElementTree.Element:
        """Construct the XML placeholder inserted for missing footnotes."""
        element_name = self.getConfig("element")
        node = ElementTree.Element(element_name)

        css_class = self.getConfig("css_class")
        if css_class:
            node.set("class", css_class)

        data_attribute = self.getConfig("data_attribute")
        if data_attribute:
            node.set(data_attribute, identifier)

        text = self.getConfig("text_template").format(id=identifier)
        if self.getConfig("link_to_list"):
            footnote_extension = self._get_footnotes_extension(pattern.md)
            separator = footnote_extension.get_separator() if footnote_extension else ":"
            anchor = ElementTree.SubElement(node, "a")
            if css_class:
                anchor.set("class", css_class)
            anchor.set("href", f"#fn{separator}{identifier}")
            anchor.text = text
        else:
            node.text = text

        return node


def makeExtension(**kwargs: Any) -> MissingFootnotesExtension:  # noqa: N802 - markdown hook
    """Entry point exposed to Python-Markdown."""
    return MissingFootnotesExtension(**kwargs)
