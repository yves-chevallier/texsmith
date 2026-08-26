"""Markdown extension providing the ``#{prefix:key}`` custom-counter syntax.

Counter series are declared in the YAML front matter and handed to the
``Markdown`` instance as ``md.texsmith_counters`` for the duration of a single
conversion (see :func:`texsmith.adapters.markdown.render_markdown`). An inline
processor turns every ``#{prefix:key}`` whose prefix is declared into an empty
``<span class="ts-counter">`` anchor; a treeprocessor then walks the finished
document tree in order, allocates the numbers — including the silent ones
carried by ``{#prefix:key}`` attribute lists — and fills the empty
``@prefix:key`` cross-reference anchors with the same formatted value.

Markers whose prefix is undeclared are left strictly alone, so Ruby or
CoffeeScript interpolations such as ``#{user.name}`` survive untouched.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree

from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.treeprocessors import Treeprocessor

from texsmith.core.counters import (
    KEY_PATTERN,
    PREFIX_PATTERN,
    CounterRegistry,
    CounterSpec,
    get_registry,
)
from texsmith.core.diagnostics import warn_author


def _warn(message: str, md: Markdown | None = None) -> None:
    """Surface an authoring defect visibly, attributed to the document."""
    warn_author(message, getattr(md, "texsmith_document_path", None))


#: ``#{prefix:key}`` — the negative lookbehind keeps ``\#{…}`` literal, and the
#: mandatory ``{`` makes a collision with the ``#[term]`` index syntax
#: impossible.
COUNTER_PATTERN = rf"(?<!\\)#\{{(?P<prefix>{PREFIX_PATTERN}):(?P<key>{KEY_PATTERN})\}}"

#: ``{#prefix:key}`` attribute lists land as a plain ``id``; the same shape is
#: also what ``@prefix:key`` references produce as ``href="#prefix:key"``.
IDENTIFIER_RE = re.compile(rf"^(?P<prefix>{PREFIX_PATTERN}):(?P<key>{KEY_PATTERN})$")


def _declared_counters(md: Markdown | None) -> dict[str, CounterSpec]:
    """Return the counter specs declared for the document being converted."""
    specs = getattr(md, "texsmith_counters", None)
    return specs if isinstance(specs, dict) else {}


class _CounterInlineProcessor(InlineProcessor):
    """Replace ``#{prefix:key}`` with an empty, identified counter span."""

    def handleMatch(  # noqa: N802 - Markdown inline API requires camelCase
        self,
        match: re.Match[str],
        data: str,
    ) -> tuple[ElementTree.Element | None, int | None, int | None]:  # type: ignore[override]
        del data
        prefix = match.group("prefix")
        key = match.group("key")

        if prefix not in _declared_counters(self.md):
            # Undeclared prefix: decline the match so python-markdown keeps the
            # source text verbatim (``#{user.name}`` and friends).
            return None, None, None

        element = ElementTree.Element("span")
        element.set("class", "ts-counter")
        element.set("id", f"{prefix}:{key}")
        element.set("data-counter", prefix)
        element.set("data-key", key)
        # The number itself is only known once the whole tree is built.
        element.text = ""
        return element, match.start(0), match.end(0)


class _CounterTreeprocessor(Treeprocessor):
    """Allocate counter values in document order and resolve references."""

    def run(self, root: ElementTree.Element) -> None:  # type: ignore[override]
        """Number every marker, then fill the matching reference anchors."""
        specs = _declared_counters(self.md)
        if not specs:
            return

        registry = get_registry()
        # The one place declarations reach the registry during a conversion;
        # the MkDocs pre-pass declares earlier so it can reserve values.
        registry.declare(specs)

        for element in root.iter():
            if element.tag == "span" and "ts-counter" in (element.get("class") or "").split():
                self._define_span(element, specs, registry)
                continue
            identifier = element.get("id")
            if identifier:
                self._define_silent(identifier, specs, registry)

        for element in root.iter():
            if element.tag == "a":
                self._resolve_reference(element, specs, registry)

    # -- passes ------------------------------------------------------------

    def _define_span(
        self,
        element: ElementTree.Element,
        specs: dict[str, CounterSpec],
        registry: CounterRegistry,
    ) -> None:
        prefix = element.get("data-counter") or ""
        key = element.get("data-key") or ""
        spec = specs.get(prefix)
        if spec is None or not key:
            return
        value, is_duplicate = registry.allocate(prefix, key)
        if is_duplicate:
            _warn(
                f"Counter '{prefix}:{key}' is defined more than once; keeping the first number.",
                self.md,
            )
        element.text = spec.render(value, key)

    def _define_silent(
        self,
        identifier: str,
        specs: dict[str, CounterSpec],
        registry: CounterRegistry,
    ) -> None:
        match = IDENTIFIER_RE.match(identifier)
        if match is None:
            return
        prefix = match.group("prefix")
        if prefix not in specs:
            return
        # ``## Title {#fw:boot}`` numbers the item without printing anything.
        registry.allocate(prefix, match.group("key"))

    def _resolve_reference(
        self,
        element: ElementTree.Element,
        specs: dict[str, CounterSpec],
        registry: CounterRegistry,
    ) -> None:
        href = element.get("href") or ""
        if not href.startswith("#"):
            return
        match = IDENTIFIER_RE.match(href[1:])
        if match is None:
            return
        prefix = match.group("prefix")
        key = match.group("key")
        if prefix not in specs:
            return
        rendered = registry.render(prefix, key)
        if rendered is None:
            _warn(f"Counter reference '@{prefix}:{key}' has no matching item.", self.md)
            return
        # An explicit link text (``[see](#fw:boot)``) wins over the number.
        if not element.text and len(element) == 0:
            element.text = rendered


class CountersExtension(Extension):
    """Register the custom-counter inline and tree processors."""

    def __init__(self, **kwargs: object) -> None:
        self.config = {
            "specs": [
                {},
                "Mapping of prefix -> CounterSpec for the document being converted.",
            ],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802 - markdown hook
        """Wire the processors and seed the per-conversion declaration slot."""
        # Two ways in: ``render_markdown`` refreshes ``md.texsmith_counters``
        # before every conversion on its cached, shared instance, while MkDocs
        # builds one throwaway ``Markdown`` per page and can only pass the
        # declarations through the extension config.
        configured = self.getConfig("specs")
        if isinstance(configured, dict) and configured:
            md.texsmith_counters = dict(configured)  # type: ignore[attr-defined]
        elif not hasattr(md, "texsmith_counters"):
            md.texsmith_counters = {}  # type: ignore[attr-defined]

        # Below ``escape`` (180) so ``\#{n:joy}`` stays literal.
        md.inlinePatterns.register(
            _CounterInlineProcessor(COUNTER_PATTERN, md), "texsmith_counters", 179
        )
        # Below ``inline`` (20) and ``attr_list`` (8): the tree is complete and
        # the ``{#prefix:key}`` identifiers have been moved onto their element.
        md.treeprocessors.register(_CounterTreeprocessor(md), "texsmith_counters", 4)


def makeExtension(**kwargs: object) -> CountersExtension:  # noqa: N802 - Markdown API hook; pragma: no cover
    return CountersExtension(**kwargs)


__all__ = ["CountersExtension", "makeExtension"]
