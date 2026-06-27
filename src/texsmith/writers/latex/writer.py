"""``LaTeXWriter`` — emit LaTeX from the TeXSmith IR.

The writer is a typed visitor over :mod:`texsmith.ir`. Each node class has an
emitter registered with :func:`~texsmith.writers.registry.writes`; a node with no emitter
raises a clear, localised error (no opaque ``AttributeError``). Emitters reuse
the existing Jinja partials through :class:`~texsmith.adapters.latex.LaTeXFormatter`
and the font-script machinery, so the produced LaTeX matches the legacy
mutate-and-flatten pipeline byte-for-byte.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from requests.utils import requote_uri as requote_url

from texsmith.ir import nodes as ir
from texsmith.writers.registry import WriterRegistry, writes

from .._ir_queries import (
    _citation_keys_from_payload,
    _find_image,
    _find_table,
    _normalise_footnote_id,
    _split_citation_keys,
)
from .escaper import _MATH_PAYLOAD_PATTERN, escape_latex_chars, escape_text_segment


if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Sequence

    from .state import WriterState


_MINTINLINE_DELIMITERS: tuple[str, ...] = (
    "|",
    "!",
    ";",
    ":",
    "+",
    "/",
    "-",
    "=",
    "~",
    "*",
    "#",
    "?",
)
_CODE_ENGINES = {"minted", "listings", "verbatim", "pygments"}
_BLOCK_MATH_ENVIRONMENTS = {"align", "align*", "equation", "equation*"}
_LANGUAGE_TOKEN = re.compile(r"^[A-Za-z0-9_+\-#.]+$")
_LONE_BOLD_LIMIT = 80


class LaTeXWriter:
    """Visitor that turns an IR document into a LaTeX string."""

    def __init__(self, state: WriterState) -> None:
        self.state = state
        self._invalid_footnotes: set[str] = set()
        cls = type(self)
        # One registry per concrete class (a subclass that adds ``@writes``
        # emitters gets its own, not the base class's cached one).
        registry = cls.__dict__.get("_registry")
        if registry is None:
            registry = WriterRegistry()
            registry.collect_from_class(cls)
            cls._registry = registry  # type: ignore[attr-defined]
        self.registry = registry

    # -- public API --------------------------------------------------------

    def write(self, document: ir.Document) -> str:
        """Render a full document IR to LaTeX."""
        self._collect_footnotes(document)
        return self._join_blocks(document.content)

    def _collect_footnotes(self, document: ir.Document) -> None:
        """Pre-pass: harvest footnote definition bodies into the state.

        Mirrors the legacy ``render_footnotes`` body collection: each
        ``Div role=footnote-def id=<fn>`` is reduced to its single-line text and
        stored in ``state.footnotes`` keyed by the normalised identifier, so
        ``footnote-ref`` sites can resolve to a ``\\footnote`` or ``\\cite``.
        """
        import warnings

        from texsmith.ir.visitor import walk

        footnotes: dict[str, str] = {}
        for node in walk(document):
            if not isinstance(node, ir.Div):
                continue
            attrs = dict(node.attrs)
            if attrs.get("role") != "footnote-def":
                continue
            footnote_id = _normalise_footnote_id(attrs.get("id"))
            if not footnote_id:
                continue
            text = self._footnote_body_text(node.content)
            lines = [line for line in text.splitlines() if line.strip()]
            if len(lines) > 1:
                warnings.warn(
                    f"Footnote '{footnote_id}' spans multiple lines and cannot be "
                    "rendered; dropping it.",
                    stacklevel=2,
                )
                # Record so the reference site is dropped silently (not warned).
                self._invalid_footnotes.add(footnote_id)
                continue
            footnotes[footnote_id] = text.strip()
        if footnotes:
            self.state.state.footnotes.update(footnotes)

    def _footnote_body_text(self, blocks: Sequence[ir.Block]) -> str:
        return self._blocks(blocks).strip()

    # -- dispatch ----------------------------------------------------------

    def emit(self, node: ir.Node) -> str:
        """Emit a single node, dispatching by type."""
        method = self.registry.method_for(node)
        if method is None:
            raise LaTeXWriteError(node)
        return getattr(self, method)(node)

    def _blocks(self, blocks: Sequence[ir.Block]) -> str:
        return self._join_blocks(blocks)

    def _join_blocks(self, blocks: Sequence[ir.Block]) -> str:
        """Join block emissions with a single newline.

        The legacy pipeline flattened the mutated soup with ``get_text()``: the
        Markdown HTML has exactly one ``\\n`` between sibling block tags, and
        each handler baked its own surrounding newlines into the replacement
        string. We reproduce that — emitters carry their own trailing newlines,
        the join contributes the inter-block ``\\n``.
        """
        merged = self._merge_script_blocks(blocks)
        parts = [self.emit(block) for block in merged]
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _merge_script_blocks(blocks: Sequence[ir.Block]) -> list[ir.Block]:
        """Merge consecutive ``Div role=script`` siblings of the same slug.

        The legacy ``_render_script_paragraphs`` grouped a run of
        ``<p data-script=slug>`` siblings into a single ``\\begin{slug}…`` env.
        """
        out: list[ir.Block] = []
        for block in blocks:
            if (
                isinstance(block, ir.Div)
                and dict(block.attrs).get("role") == "script"
                and out
                and isinstance(out[-1], ir.Div)
                and dict(out[-1].attrs) == dict(block.attrs)
            ):
                prev = out[-1]
                out[-1] = ir.Div(content=(*prev.content, *block.content), attrs=prev.attrs)
                continue
            out.append(block)
        return out

    def _inlines(self, inlines: Sequence[ir.Inline]) -> str:
        return "".join(self.emit(node) for node in inlines)

    def render_inlines(self, inlines: Sequence[ir.Inline]) -> str:
        """Public inline-rendering entry point (used by the table emitter)."""
        return self._inlines(inlines)

    # -- font scripts helpers ---------------------------------------------

    def _moving(
        self,
        text: str | None,
        *,
        include_whitespace: bool = True,
        escape: bool = True,
        wrap_scripts: bool = False,
    ) -> str:
        from texsmith.fonts.scripts import render_moving_text

        return (
            render_moving_text(
                text,
                self.state,
                include_whitespace=include_whitespace,
                legacy_accents=self.state.legacy_accents,
                escape=escape,
                wrap_scripts=wrap_scripts,
            )
            or ""
        )

    def _script_wrap_block(self, rendered: str, raw_text: str) -> str:
        """Apply paragraph-level script wrapping to assembled inline LaTeX.

        Mirrors ``render_paragraphs``: scripts are only wrapped (and the text
        re-escaped) when the *raw* source had no backslash and no math.
        """
        contains_math = bool(_MATH_PAYLOAD_PATTERN.search(raw_text))
        do_escape = "\\" not in raw_text and not contains_math
        return self._moving(
            rendered,
            include_whitespace=True,
            escape=False,
            wrap_scripts=do_escape,
        )

    # ----------------------------------------------------------------- #
    # Inline emitters
    # ----------------------------------------------------------------- #

    def _emoji_renderer(self, token: str) -> str:
        from texsmith.adapters.transformers import fetch_image
        from texsmith.core.exceptions import TransformerExecutionError

        runtime = self.state.runtime
        mode = _str_runtime(runtime.get("emoji_mode"), "black")
        command = _str_runtime(runtime.get("emoji_command"), r"\texsmithEmoji")
        if mode != "artifact":
            return f"{command}{{{token}}}" if token else ""
        url = (
            "https://twemoji.maxcdn.com/v/latest/svg/"
            + "-".join(f"{ord(c):x}" for c in token)
            + ".svg"
        )
        try:
            user_agent = _str_runtime(runtime.get("http_user_agent"), "")
            options = {"user_agent": user_agent} if user_agent else {}
            artefact = fetch_image(url, output_dir=self.state.assets.output_root, **options)
        except TransformerExecutionError:
            from .escaper import prepare_plain_text

            return prepare_plain_text(token, legacy_accents=self.state.legacy_accents)
        stored = self.state.assets.register(url, artefact)
        return self.state.formatter.render_template("icon", self.state.assets.latex_path(stored))

    def _text(self, text: str) -> str:
        """Escape a plain-text run, preserving embedded math payloads.

        Mirrors the legacy ``escape_plain_text``: ``$…$`` / ``\\(…\\)`` / ``\\[…\\]``
        and math environments are kept verbatim; only the surrounding prose is
        escaped (and emoji-segmented).
        """
        if not text:
            return text
        # Raw ``\keystroke{…}`` / ``\keystrokes{…}`` typed directly in the source
        # is left verbatim, mirroring the legacy ``escape_plain_text`` guard.
        if "\\keystroke{" in text or "\\keystrokes{" in text:
            return text
        matches = list(_MATH_PAYLOAD_PATTERN.finditer(text))
        if not matches:
            return self._escape_segment(text)
        parts: list[str] = []
        cursor = 0
        for match in matches:
            if match.start() > cursor:
                parts.append(self._escape_segment(text[cursor : match.start()]))
            parts.append(match.group(0))
            cursor = match.end()
        if cursor < len(text):
            parts.append(self._escape_segment(text[cursor:]))
        return "".join(parts)

    def _escape_segment(self, text: str) -> str:
        return escape_text_segment(
            text,
            legacy_accents=self.state.legacy_accents,
            emoji_renderer=self._emoji_renderer,
        )

    @writes(ir.Str)
    def _str(self, node: ir.Str) -> str:
        return self._text(node.text)

    @writes(ir.Space)
    def _space(self, _node: ir.Space) -> str:
        return " "

    @writes(ir.SoftBreak)
    def _softbreak(self, _node: ir.SoftBreak) -> str:
        return "\n"

    @writes(ir.LineBreak)
    def _linebreak(self, _node: ir.LineBreak) -> str:
        return "\\"

    @writes(ir.Emph)
    def _emph(self, node: ir.Emph) -> str:
        return self.state.formatter.render_template("italic", text=self._inlines(node.content))

    @writes(ir.Strong)
    def _strong(self, node: ir.Strong) -> str:
        return self.state.formatter.render_template("strong", text=self._inlines(node.content))

    @writes(ir.Strikeout)
    def _strikeout(self, node: ir.Strikeout) -> str:
        return self.state.formatter.render_template(
            "strikethrough", text=self._inlines(node.content)
        )

    @writes(ir.Underline)
    def _underline(self, node: ir.Underline) -> str:
        return self.state.formatter.render_template("underline", text=self._inlines(node.content))

    @writes(ir.Highlight)
    def _highlight(self, node: ir.Highlight) -> str:
        return self.state.formatter.render_template("highlight", text=self._inlines(node.content))

    @writes(ir.Subscript)
    def _subscript(self, node: ir.Subscript) -> str:
        return self.state.formatter.render_template("subscript", text=self._inlines(node.content))

    @writes(ir.Superscript)
    def _superscript(self, node: ir.Superscript) -> str:
        return self.state.formatter.render_template("superscript", text=self._inlines(node.content))

    @writes(ir.SmallCaps)
    def _smallcaps(self, node: ir.SmallCaps) -> str:
        # The legacy smallcaps handler captured ``get_text()`` at INLINE time:
        # inline code/math (rendered in the earlier PRE phase) survive, but the
        # emphasis wrappers (bold/italic/underline…), processed *after*, are
        # flattened away. Reproduce that selective flattening.
        return self.state.formatter.render_template(
            "smallcaps", text=self._smallcaps_inner(node.content)
        )

    def _smallcaps_inner(self, content: Sequence[ir.Inline]) -> str:
        parts: list[str] = []
        for child in content:
            if isinstance(child, (ir.Code, ir.Math, ir.RawInline)):
                parts.append(self.emit(child))
            elif isinstance(
                child,
                (ir.Emph, ir.Strong, ir.Underline, ir.Strikeout, ir.Highlight, ir.SmallCaps),
            ):
                parts.append(self._smallcaps_inner(child.content))
            elif isinstance(child, ir.Str):
                parts.append(self._text(child.text))
            elif isinstance(child, (ir.Space, ir.SoftBreak)):
                parts.append(self.emit(child))
            else:
                parts.append(self.emit(child))
        return "".join(parts)

    @writes(ir.Quoted)
    def _quoted(self, node: ir.Quoted) -> str:
        return self.state.formatter.render_template("enquote", text=self._inlines(node.content))

    @writes(ir.Code)
    def _code(self, node: ir.Code) -> str:
        formatter = self.state.formatter
        engine = self._code_engine()
        if not node.lang:
            return formatter.render_template("codeinlinett", node.text)
        if engine == "minted" and self._pick_minted_delimiter(node.text):
            self.state.state.requires_shell_escape = True
            return formatter.render_template(
                "codeinline", language=node.lang or "text", text=node.text, engine=engine
            )
        return formatter.render_template(
            "codeinline",
            language=node.lang or "text",
            text=node.text,
            engine=engine,
            state=self.state.state,
        )

    @writes(ir.Math)
    def _math(self, node: ir.Math) -> str:
        if node.display:
            payload = node.text.strip()
            if _payload_is_block_environment(payload):
                return f"\n{payload}\n"
            return f"\n$$\n{payload}\n$$\n"
        return f"${node.text}$"

    @writes(ir.Link)
    def _link(self, node: ir.Link) -> str:
        return self._render_link(node.content, node.target, node.title)

    @writes(ir.Cite)
    def _cite(self, node: ir.Cite) -> str:
        for key in node.keys:
            self.state.state.record_citation(key)
        return self.state.formatter.render_template("citation", key=",".join(node.keys))

    @writes(ir.Note)
    def _note(self, node: ir.Note) -> str:
        body = self._blocks(node.content).strip()
        return self.state.formatter.render_template("footnote", body)

    @writes(ir.Image)
    def _image(self, node: ir.Image) -> str:
        return self._render_image(node, template=None, label=None)

    @writes(ir.IndexEntry)
    def _index(self, node: ir.IndexEntry) -> str:
        return self._render_index_entry(node)

    @writes(ir.TexLogo)
    def _texlogo(self, node: ir.TexLogo) -> str:
        from texsmith.extensions.texlogos.specs import alias_mapping, iter_specs

        slug_lookup = {spec.slug: spec for spec in iter_specs()}
        spec = slug_lookup.get(node.name) or alias_mapping().get(node.name)
        if spec is not None:
            return spec.command
        # Fall back to a sensible default for the {LaTeX} helper.
        return r"\LaTeX{}"

    @writes(ir.Keystroke)
    def _keystroke(self, node: ir.Keystroke) -> str:
        return self.state.formatter.render_template("keystroke", list(node.keys))

    @writes(ir.MarginNote)
    def _marginnote(self, node: ir.MarginNote) -> str:
        text = self._blocks_inline(node.content).strip()
        if not text:
            return ""
        if node.side is ir.MarginSide.LEFT:
            return rf"{{\reversemarginpar\marginnote{{{text}}}}}"
        return rf"\marginnote{{{text}}}"

    @writes(ir.RawInline)
    def _raw_inline(self, node: ir.RawInline) -> str:
        return node.text if node.format == "latex" else ""

    @writes(ir.Span)
    def _span(self, node: ir.Span) -> str:
        return self._render_span(node)

    # ----------------------------------------------------------------- #
    # Block emitters
    # ----------------------------------------------------------------- #

    @writes(ir.Para)
    def _para(self, node: ir.Para) -> str:
        lead = self._lone_bold_lead(node)
        if lead is not None:
            return lead
        rendered = self._inlines(node.content)
        if not rendered.strip():
            return ""
        wrapped = self._script_wrap_block(rendered, rendered)
        return f"{wrapped}\n"

    def _lone_bold_lead(self, node: ir.Para) -> str | None:
        """Promote a standalone short-bold paragraph to a ``\\tslead`` lead-in.

        Mirrors the legacy ``render_lone_bold_paragraph``: a paragraph whose
        sole content is a single ``<strong>`` of fewer than 80 plain characters
        becomes a no-indent bold lead-in.
        """
        if len(node.content) != 1 or not isinstance(node.content[0], ir.Strong):
            return None
        strong = node.content[0]
        plain_text = self._plain_text(strong.content).strip()
        if not plain_text or len(plain_text) >= _LONE_BOLD_LIMIT:
            return None
        contains_math = bool(_MATH_PAYLOAD_PATTERN.search(plain_text))
        escape_text = "\\" not in plain_text and not contains_math
        rendered = self._moving(
            plain_text,
            include_whitespace=False,
            escape=escape_text,
            wrap_scripts=escape_text,
        )
        lead = self.state.formatter.render_template("lead", text=rendered)
        return f"{lead}\n"

    @writes(ir.Plain)
    def _plain(self, node: ir.Plain) -> str:
        return self._inlines(node.content)

    @writes(ir.Header)
    def _header(self, node: ir.Header) -> str:
        from slugify import slugify

        runtime = self.state.runtime
        if runtime.get("drop_title"):
            runtime["drop_title"] = False
            return self.state.formatter.render_template("pagestyle", text="plain")

        rendered = self._inlines(node.content)
        text = self._script_wrap_block_heading(rendered)
        # A heading is typeset as a sectioning-command argument (``\section{…}``),
        # which cannot contain a paragraph break. Rich headings (e.g. mkdocstrings
        # members carrying a ``<small>`` label) can render to multi-line content,
        # so collapse internal newline runs to single spaces.
        text = re.sub(r"\s*\n\s*", " ", text).strip()
        # Legacy slug came from ``get_text(strip=True)`` of the POST-phase soup,
        # i.e. the already inline-rendered text (``\enquote{…}`` included).
        plain_text = _strip_text(rendered)
        base_level = runtime.get("base_level", 0)
        rendered_level = node.level + base_level - 1
        ref = node.identifier or (slugify(plain_text, separator="-") or None)
        numbered = runtime.get("numbered", True)
        latex = self.state.formatter.render_template(
            "heading", text=text, level=rendered_level, ref=ref, numbered=numbered
        )
        self.state.state.add_heading(level=rendered_level, text=plain_text, ref=ref)
        return latex

    @writes(ir.CodeBlock)
    def _code_block(self, node: ir.CodeBlock) -> str:
        if node.lang == "mermaid":
            return self._render_mermaid(node.text)
        engine = self._code_engine()
        code_text = node.text
        if engine == "minted":
            code_text = code_text.replace("{", r"\{").replace("}", r"\}")
        if code_text and not code_text.endswith("\n"):
            code_text += "\n"
        baselinestretch = 0.5 if _is_ascii_art(code_text) else None
        self.state.state.requires_shell_escape = (
            self.state.state.requires_shell_escape or engine == "minted"
        )
        filename = node.filename or None
        if filename:
            # The filename is typeset as the code block's title, so LaTeX
            # specials in it (e.g. ``_`` in ``bubble_sort.py``) must be escaped.
            filename = escape_latex_chars(filename, legacy_accents=self.state.legacy_accents)
        return self.state.formatter.render_template(
            "codeblock",
            code=code_text,
            language=node.lang or "text",
            lineno=node.lineno,
            filename=filename,
            highlight=list(node.highlight),
            baselinestretch=baselinestretch,
            engine=engine,
            state=self.state.state,
        )

    @writes(ir.BlockQuote)
    def _blockquote(self, node: ir.BlockQuote) -> str:
        # Mirror the legacy ``get_text()`` of ``<blockquote>\n<p>…</p>\n</bq>``:
        # a leading newline from the HTML plus each inner block's trailing
        # newline, which the ``displayquote`` partial pads to blank lines.
        inner = self._blocks(node.content)
        if inner and not inner.endswith("\n"):
            inner += "\n"
        return self.state.formatter.render_template("blockquote", f"\n{inner}")

    @writes(ir.BulletList)
    def _bullet_list(self, node: ir.BulletList) -> str:
        items, checkboxes = self._list_items(node.items)
        if any(checkboxes):
            choices = list(zip((c > 0 for c in checkboxes), items, strict=False))
            return self.state.formatter.render_template("choices", items=choices)
        return self.state.formatter.render_template("unordered_list", items=items)

    @writes(ir.OrderedList)
    def _ordered_list(self, node: ir.OrderedList) -> str:
        items, _checkboxes = self._list_items(node.items)
        return self.state.formatter.render_template("ordered_list", items=items)

    @writes(ir.DefinitionList)
    def _definition_list(self, node: ir.DefinitionList) -> str:
        items: list[tuple[str | None, str]] = []
        for item in node.items:
            term = self._inlines(item.term).strip() or None
            for definition in item.definitions:
                body = self._blocks(definition).strip()
                items.append((term, body))
            if not item.definitions:
                items.append((term, ""))
        return self.state.formatter.render_template("description_list", items=items)

    @writes(ir.HorizontalRule)
    def _hr(self, _node: ir.HorizontalRule) -> str:
        return self.state.formatter.render_template("horizontal_rule")

    @writes(ir.Figure)
    def _figure(self, node: ir.Figure) -> str:
        return self._render_figure(node)

    @writes(ir.Admonition)
    def _admonition(self, node: ir.Admonition) -> str:
        return self._render_admonition(node)

    @writes(ir.ProgressBar)
    def _progressbar(self, node: ir.ProgressBar) -> str:
        from texsmith.extensions.progressbar.renderer import _compose_latex

        label_text = (
            self._inlines(node.label).strip() if node.label else f"{node.fraction * 100:g}%"
        )
        return _compose_latex(node.fraction, label_text, thin=node.thin)

    @writes(ir.Table)
    def _table(self, node: ir.Table) -> str:
        return self._render_table(node)

    @writes(ir.Div)
    def _div(self, node: ir.Div) -> str:
        return self._render_div(node)

    @writes(ir.RawBlock)
    def _raw_block(self, node: ir.RawBlock) -> str:
        if node.format != "latex":
            return ""
        return node.text

    @writes(ir.Document)
    def _document(self, node: ir.Document) -> str:
        return self._blocks(node.content)

    # ----------------------------------------------------------------- #
    # Helpers
    # ----------------------------------------------------------------- #

    def _blocks_inline(self, blocks: Sequence[ir.Block]) -> str:
        """Render block content that is conceptually inline (margin notes)."""
        return "".join(self.emit(block) for block in blocks)

    def _plain_text(self, inlines: Iterable[ir.Inline]) -> str:
        """Best-effort plain text of an inline run (for slugs/headings list)."""
        from texsmith.ir.visitor import walk

        parts: list[str] = []
        for inline in inlines:
            for node in walk(inline):
                if isinstance(node, ir.Str):
                    parts.append(node.text)
                elif isinstance(node, ir.Space):
                    parts.append(" ")
        return "".join(parts)

    def _script_wrap_block_heading(self, rendered: str) -> str:
        do_escape = "\\" not in rendered
        return self._moving(rendered, include_whitespace=True, escape=False, wrap_scripts=do_escape)

    def _code_engine(self) -> str:
        runtime_code = self.state.runtime.get("code")
        engine: str | None = None
        if isinstance(runtime_code, dict):
            raw = runtime_code.get("engine")
            engine = raw if isinstance(raw, str) else None
        elif isinstance(runtime_code, str):
            engine = runtime_code
        candidate = (engine or "").strip().lower()
        return candidate if candidate in _CODE_ENGINES else "pygments"

    @staticmethod
    def _pick_minted_delimiter(text: str) -> str | None:
        for delimiter in _MINTINLINE_DELIMITERS:
            if delimiter not in text:
                return delimiter
        return None

    def _list_items(self, items: Sequence[Sequence[ir.Block]]) -> tuple[list[str], list[int]]:
        rendered: list[str] = []
        checkboxes: list[int] = []
        for item in items:
            blocks = list(item)
            marker = 0
            if blocks and isinstance(blocks[0], ir.Div):
                attrs = dict(blocks[0].attrs)
                if attrs.get("role") == "task-marker":
                    marker = 1 if attrs.get("checked") == "true" else -1
                    blocks = blocks[1:]
            text = self._render_list_item_body(blocks)
            if marker == 0:
                # Legacy ``render_lists`` also recognised literal ``[ ]`` / ``[x]``
                # text prefixes when no ``<input type=checkbox>`` was present.
                if text.startswith("[ ]"):
                    marker = -1
                    text = text[3:].strip()
                elif text.startswith(("[x]", "[X]")):
                    marker = 1
                    text = text[3:].strip()
            rendered.append(text)
            checkboxes.append(marker)
        return rendered, checkboxes

    def _render_list_item_body(self, blocks: Sequence[ir.Block]) -> str:
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, (ir.Plain, ir.Para)):
                parts.append(self._inlines(block.content))
            else:
                parts.append(self.emit(block))
        text = "".join(parts).strip()
        # Match legacy ``_li_text``: ensure nested list environments start on
        # their own line.
        return re.sub(r"(\S)(\\begin\{(?:itemize|enumerate|description)\})", r"\1\n\2", text)

    def _render_link(self, content: Sequence[ir.Inline], target: str, _title: str) -> str:
        from urllib.parse import urlparse

        formatter = self.state.formatter
        # A link wrapping a single image becomes a figure whose includegraphics
        # is itself wrapped in ``\href`` (the figure template's ``link`` arg).
        if len(content) == 1 and isinstance(content[0], ir.Image):
            return self._render_image(content[0], template=None, label=None, link=target)
        text = self._inlines(content)
        parsed = urlparse(target)
        scheme = (parsed.scheme or "").lower()
        fragment = parsed.fragment.strip() if parsed.fragment else ""

        if scheme in {"http", "https"}:
            return formatter.render_template("href", text=text, url=requote_url(target))
        if scheme:
            from texsmith.core.exceptions import InvalidNodeError

            raise InvalidNodeError(f"Unsupported link scheme '{scheme}' for '{target}'.")
        if target.startswith("#"):
            return formatter.render_template("ref", text, ref=target[1:])
        if target:
            resolved = self._resolve_local_target(target)
            if resolved is None:
                from texsmith.core.exceptions import AssetMissingError

                raise AssetMissingError(f"Unable to resolve link target '{target}'")
            from texsmith.writers.latex.links import _infer_heading_reference

            target_ref = fragment or _infer_heading_reference(resolved)
            if target_ref:
                return formatter.render_template("ref", text or "", ref=target_ref)
            content_bytes = resolved.read_bytes()
            from hashlib import sha256

            reference = f"snippet:{sha256(content_bytes).hexdigest()}"
            self.state.state.register_snippet(
                reference,
                {
                    "path": resolved,
                    "content": content_bytes,
                    "format": resolved.suffix[1:] if resolved.suffix else "",
                },
            )
            return formatter.render_template("ref", text or "extrait", ref=reference)
        return text

    def _resolve_local_target(self, href: str):  # noqa: ANN202
        from texsmith.writers.latex.links import _resolve_local_target

        return _resolve_local_target(self.state, href)

    # -- span dispatch by role --------------------------------------------

    def _render_span(self, node: ir.Span) -> str:
        attrs = dict(node.attrs)
        role = attrs.get("role", "")
        formatter = self.state.formatter
        if role == "abbr":
            return self._render_abbr(node, attrs.get("title", ""))
        if role == "critic-deletion":
            return formatter.render_template("deletion", text=self._inlines(node.content))
        if role == "critic-addition":
            return formatter.render_template("addition", text=self._inlines(node.content))
        if role == "critic-highlight":
            return formatter.render_template("highlight", text=self._inlines(node.content))
        if role == "critic-comment":
            return formatter.render_template("comment", text=self._inlines(node.content))
        if role == "critic-substitution":
            return self._render_critic_substitution(node)
        if role == "script":
            return self._render_script_span(node, attrs.get("script", ""))
        if role == "regex":
            return self._render_regex(node, attrs.get("href", ""))
        if role == "label":
            return formatter.render_template("label", attrs.get("id", ""))
        if role == "footnote-ref":
            return self._render_footnote_ref(node, attrs.get("ref", ""))
        if role == "emoji":
            return self._render_emoji_span(node)
        # Plain / transparent span: render children.
        return self._inlines(node.content)

    def _render_abbr(self, node: ir.Span, title: str) -> str:
        term = self._plain_text(node.content).strip()
        if not term:
            return ""
        description = title.strip()
        if not description:
            return escape_latex_chars(term, legacy_accents=self.state.legacy_accents)
        key = self.state.state.remember_abbreviation(term, description) or term
        return f"\\acrshort{{{key}}}"

    def _render_critic_substitution(self, node: ir.Span) -> str:
        deleted = ""
        inserted = ""
        for child in node.content:
            if isinstance(child, ir.Strikeout):
                deleted = self._inlines(child.content)
            elif isinstance(child, ir.Underline):
                inserted = self._inlines(child.content)
            elif isinstance(child, ir.Span):
                sub = dict(child.attrs).get("role", "")
                if sub == "critic-deletion":
                    deleted = self._inlines(child.content)
                elif sub == "critic-addition":
                    inserted = self._inlines(child.content)
        return self.state.formatter.render_template(
            "substitution", original=deleted, replacement=inserted
        )

    def _render_script_span(self, node: ir.Span, slug: str) -> str:
        from texsmith.fonts.scripts import record_script_usage_for_slug

        raw_text = self._plain_text(node.content)
        if not raw_text:
            return ""
        record_script_usage_for_slug(slug, raw_text, self.state)
        payload = escape_latex_chars(raw_text, legacy_accents=self.state.legacy_accents)
        return f"\\text{slug}{{{payload}}}"

    def _render_regex(self, node: ir.Span, href: str) -> str:
        code = self._regex_code(node)
        code = code.replace("&", "\\&").replace("#", "\\#")
        return self.state.formatter.render_template("regex", code, url=requote_url(href))

    def _regex_code(self, node: ir.Span) -> str:
        # The legacy handler used the <code> text when present, else the raw text.
        for child in node.content:
            if isinstance(child, ir.Code):
                return child.text
        return self._plain_text(node.content)

    def _render_footnote_ref(self, node: ir.Span, ref: str) -> str:
        footnote_id = _normalise_footnote_id(ref)
        if footnote_id in self._invalid_footnotes:
            # Body was dropped (e.g. multi-line) — drop the marker silently.
            return ""
        bibliography = self.state.state.bibliography
        payload = self.state.state.footnotes.get(footnote_id)

        # A footnote body that is purely a comma-separated citation key list
        # resolves to a citation (with on-demand DOI materialisation), mirroring
        # the legacy ``render_footnotes`` recovery path.
        keys = _citation_keys_from_payload(payload)
        if not keys:
            keys = _split_citation_keys(footnote_id)
        if keys:
            self._ensure_doi_entries(keys)
            if all(key in bibliography for key in keys):
                for key in keys:
                    self.state.state.record_citation(key)
                return self.state.formatter.render_template("citation", key=",".join(keys))
        if footnote_id in bibliography:
            import warnings

            if payload and not _is_bibliography_placeholder(payload):
                warnings.warn(
                    f"Conflicting bibliography definition for '{footnote_id}'.",
                    stacklevel=2,
                )
            self.state.state.record_citation(footnote_id)
            return self.state.formatter.render_template("citation", key=footnote_id)
        if payload:
            return self.state.formatter.render_template("footnote", payload)
        # Unresolved reference: warn (mirroring the legacy render_footnotes) and
        # keep the rendered marker text.
        if footnote_id:
            import warnings

            warnings.warn(
                f"Reference to '{footnote_id}' is not in your bibliography...",
                stacklevel=2,
            )
        return self._inlines(node.content)

    def _ensure_doi_entries(self, keys: list[str]) -> None:
        from texsmith.writers.latex.doi import _ensure_doi_entries

        _ensure_doi_entries(keys, self.state)

    def _render_emoji_span(self, node: ir.Span) -> str:
        token = self._plain_text(node.content)
        return self._emoji_renderer(token)

    def _render_index_entry(self, node: ir.IndexEntry) -> str:
        from texsmith.extensions.index.registry import get_registry
        from texsmith.extensions.index.renderer import (
            _apply_style,
            _format_tag,
            _strip_formatting,
        )

        legacy = self.state.legacy_accents
        formatted_tags = [_format_tag(tag, legacy=legacy) for tag in node.path]
        if node.style and formatted_tags:
            formatted_tags[-1] = _apply_style(formatted_tags[-1], node.style)
        sort_tags = [_strip_formatting(tag) for tag in node.path]
        entries: list[str] = []
        for f_tag, s_tag in zip(formatted_tags, sort_tags, strict=True):
            escaped_s_tag = escape_latex_chars(s_tag, legacy_accents=legacy)
            entries.append(f_tag if f_tag == escaped_s_tag else f"{escaped_s_tag}@{f_tag}")
        entry_str = "!".join(entries)
        visible_text = self._plain_text(node.visible)
        latex = self.state.formatter.render_template(
            "index",
            visible_text,
            entry=entry_str,
            style="",
            styled_entry=None,
            registry=node.registry or None,
        )
        get_registry().add(tuple(sort_tags))
        self.state.state.has_index_entries = True
        self.state.state.index_entries.append(tuple(sort_tags))
        return latex

    # -- div dispatch by role ---------------------------------------------

    def _render_div(self, node: ir.Div) -> str:
        attrs = dict(node.attrs)
        role = attrs.get("role", "")
        if role == "multicolumn":
            columns = int(attrs.get("columns", "2"))
            text = self._blocks(node.content).strip()
            return self.state.formatter.render_template("multicolumn", text, columns=columns)
        if role == "epigraph":
            return self._render_epigraph(node, attrs.get("source"))
        if role == "tabbed-set":
            return "\n".join(part for part in (self.emit(c) for c in node.content) if part)
        if role == "tab":
            # Legacy tabbed content prefixed each block with a bold label
            # paragraph (``\textbf{title}\par``) then the block content.
            title = escape_latex_chars(
                attrs.get("title", ""), legacy_accents=self.state.legacy_accents
            )
            body = self._blocks(node.content)
            return f"\\textbf{{{title}}}\\par\n\n{body}"
        if role == "script":
            return self._render_script_paragraphs(node, attrs.get("script", ""))
        if role == "snippet":
            return self._render_snippet(attrs.get("html", ""))
        if role == "diagram":
            width = attrs.get("width") or None
            source_hint = attrs.get("source")
            for child in node.content:
                if isinstance(child, ir.CodeBlock) and child.lang == "mermaid":
                    diagram = child.text
                    if source_hint:
                        loaded = self._load_mermaid_source(source_hint)
                        if loaded is not None:
                            diagram = loaded
                    return self._render_mermaid(diagram, width=width)
            return self._blocks(node.content)
        if role in {"footnotes", "footnote-def"}:
            # Footnote definition bodies are harvested in the write() pre-pass
            # and resolved at footnote-ref sites; the containers emit nothing.
            return ""
        if role == "table-fallback":
            return self._blocks(node.content)
        if role == "task-marker":
            return ""
        # Generic / unknown container: render children transparently.
        return self._blocks(node.content)

    def _render_epigraph(self, node: ir.Div, source: str | None) -> str:
        text = self._blocks(node.content)
        return self.state.formatter.render_template("epigraph", text=text, source=source or None)

    def _render_script_paragraphs(self, node: ir.Div, slug: str) -> str:
        from texsmith.fonts.scripts import record_script_usage_for_slug

        bodies: list[str] = []
        plains: list[str] = []
        for block in node.content:
            if isinstance(block, ir.Para):
                raw = self._plain_text(block.content)
                if not raw.strip():
                    continue
                bodies.append(escape_latex_chars(raw, legacy_accents=self.state.legacy_accents))
                plains.append(raw)
        record_script_usage_for_slug(slug, "\n\n".join(plains), self.state)
        content = "\n\n".join(bodies)
        return f"\\begin{{{slug}}}\n{content}\n\\end{{{slug}}}\n\n"

    # -- admonition / callout ---------------------------------------------

    def _render_admonition(self, node: ir.Admonition) -> str:
        from texsmith.core.callouts import DEFAULT_CALLOUTS

        aliases = {"seealso": "info"}
        kind = aliases.get(node.kind, node.kind)
        definitions = self.state.runtime.get("callouts_definitions") or DEFAULT_CALLOUTS
        if kind not in definitions:
            emitter = self.state.runtime.get("emitter")
            if emitter is not None and getattr(emitter, "warning", None):
                emitter.warning(f"Unknown callout/admonition type '{kind}', using default.")
            kind = "default"
        title = self._inlines(node.title)
        previous = self.state.runtime.get("figure_template")
        self.state.runtime["figure_template"] = "figure_tcolorbox"
        try:
            content = self._blocks(node.content).strip()
        finally:
            if previous is None:
                self.state.runtime.pop("figure_template", None)
            else:
                self.state.runtime["figure_template"] = previous
        self.state.state.callouts_used = True
        return self.state.formatter.render_template("callout", content, title=title, type=kind)

    # -- figures / images -------------------------------------------------

    def _render_figure(self, node: ir.Figure) -> str:
        from texsmith.core.exceptions import InvalidNodeError

        image = _find_image(node.content)
        caption_text = self._inlines(node.caption).strip() if node.caption else None
        if image is None:
            # A ``<figure>`` wrapping a table (pymdownx.blocks.caption): merge
            # the figcaption into the table caption and render the table.
            table = _find_table(node.content)
            if table is not None:
                merged = table
                if node.caption and not table.caption:
                    merged = ir.Table(
                        model=table.model,
                        caption=node.caption,
                        label=node.identifier or table.label,
                        cells=table.cells,
                        env=getattr(table, "env", ""),
                        colspec=getattr(table, "colspec", ""),
                        width=getattr(table, "width", ""),
                        placement=getattr(table, "placement", ""),
                    )
                return self._render_table(merged)
            raise InvalidNodeError("Figure missing <img> element")
        # A ``<figure>`` carries an already-rendered (escaped) inline caption;
        # the legacy ``render_figures`` passed it straight to the partial, with
        # the image ``alt`` as the short caption — no further ``render_moving``.
        return self._render_image(
            image,
            template=None,
            label=node.identifier or None,
            rendered_caption=caption_text,
        )

    def _render_image(
        self,
        node: ir.Image,
        *,
        template: str | None,
        label: str | None,
        rendered_caption: str | None = None,
        link: str | None = None,
    ) -> str:
        from texsmith.adapters.html_utils import is_valid_url, resolve_asset_path
        from texsmith.core.exceptions import AssetMissingError
        from texsmith.writers.latex.assets import (
            store_local_image_asset,
            store_remote_image_asset,
        )

        runtime = self.state.runtime
        alt_text = self._plain_text(node.alt).strip() if node.alt else None
        is_figure = rendered_caption is not None
        # Bare image: caption is the raw title (else alt), to be script-wrapped.
        raw_caption = rendered_caption or (node.title.strip() if node.title else None)
        if not raw_caption:
            raw_caption = alt_text
        if not runtime.get("copy_assets", True):
            return (raw_caption or alt_text or "[image]").strip() or "[image]"

        src = _strip_mkdocs_theme_variant(node.src)
        if not src:
            raise AssetMissingError("Image without 'src' attribute")

        # An image whose source is a Mermaid diagram (a ``.mmd``/``.mermaid``
        # file or a mermaid.live/ink share URL) renders as a diagram, not a
        # bitmap, mirroring the legacy ``render_images`` mermaid branch.
        mermaid = self._load_mermaid_source(src)
        if mermaid is not None:
            template_name = template or runtime.get("figure_template", "figure")
            # Legacy ``render_images`` used only the image *title* as the mermaid
            # caption (never the alt text).
            mermaid_caption = node.title.strip() if node.title else None
            return self._render_mermaid(
                mermaid, width=node.width or None, template=template_name, caption=mermaid_caption
            )

        if is_valid_url(src):
            stored = store_remote_image_asset(self.state, src)
        else:
            resolved = self._resolve_asset_path(src, resolve_asset_path)
            if resolved is None:
                raise AssetMissingError(f"Unable to resolve image asset '{src}'")
            stored = store_local_image_asset(self.state, resolved)

        # Drop the short caption when the full caption is longer than the alt.
        short_source = alt_text
        if short_source and raw_caption and len(raw_caption) > len(short_source):
            short_source = None

        template_name = template or runtime.get("figure_template", "figure")
        asset_path = self.state.assets.latex_path(stored)
        if is_figure:
            # Caption already rendered inline (escaped); legacy passed the raw
            # ``alt`` attribute as the short caption without further escaping.
            caption = raw_caption
            short = short_source or None
        else:
            caption = self._moving(raw_caption, wrap_scripts=True) if raw_caption else None
            short = self._moving(short_source, wrap_scripts=True) if short_source else None
        safe_link = None
        if link:
            from texsmith.writers.latex.escaper import escape_latex_chars

            safe_link = escape_latex_chars(
                requote_url(link), legacy_accents=self.state.legacy_accents
            )
        return self.state.formatter.render_template(
            template_name,
            path=asset_path,
            caption=caption or None,
            shortcaption=short,
            label=label,
            width=node.width or None,
            link=safe_link,
        )

    def _resolve_asset_path(self, src: str, resolve_asset_path):  # noqa: ANN001, ANN202
        from pathlib import Path

        runtime = self.state.runtime
        runtime_dir = runtime.get("source_dir")
        if runtime_dir is not None:
            candidate = Path(runtime_dir) / src
            if candidate.exists():
                return candidate.resolve()
        document_path = runtime.get("document_path")
        if document_path is not None:
            resolved = resolve_asset_path(Path(document_path), src)
            if resolved is not None:
                return resolved
        project_dir = getattr(self.state.config, "project_dir", None)
        if project_dir:
            candidate = Path(project_dir) / src
            if candidate.exists():
                return candidate.resolve()
        return None

    def _load_mermaid_source(self, src: str):  # noqa: ANN202
        """Return the Mermaid diagram body if ``src`` references one, else None."""
        from texsmith.writers.latex.media import _load_mermaid_diagram

        payload = _load_mermaid_diagram(self.state, src)
        if payload is None:
            return None
        diagram, _origin = payload
        return diagram

    def _render_mermaid(
        self,
        source: str,
        width: str | None = None,
        template: str | None = None,
        caption: str | None = None,
    ) -> str:
        # Delegate to the shared diagram helper: it handles the converter
        # backend, mermaid config, the ``%% caption`` header, the no-copy
        # placeholder, and the failure fallback + warning emission.
        from texsmith.writers.latex.media import _render_mermaid_diagram

        node = _render_mermaid_diagram(
            self.state,
            source,
            template=template,
            caption=caption,
            width=width,
        )
        return "" if node is None else str(node)

    def _render_snippet(self, html: str) -> str:
        """Render a preserved ``.snippet`` element via the snippet compiler."""
        from texsmith.adapters.plugins.snippet import render_snippet_latex

        return render_snippet_latex(html, self.state)

    # -- tables -----------------------------------------------------------

    def _render_table(self, node: ir.Table) -> str:
        from .tables import render_table

        return render_table(self, node)


class LaTeXWriteError(RuntimeError):
    """Raised when an IR node type has no LaTeX emitter registered."""

    def __init__(self, node: object) -> None:
        super().__init__(
            f"No LaTeX emitter registered for IR node {type(node).__name__!r} (backend: latex)."
        )
        self.node = node


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #


def _str_runtime(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _payload_is_block_environment(payload: str) -> bool:
    stripped = payload.lstrip()
    match = re.match(r"\\begin\{([^}]+)\}", stripped)
    return bool(match and match.group(1).lower() in _BLOCK_MATH_ENVIRONMENTS)


def _is_ascii_art(payload: str) -> bool:
    return any(c in payload for c in ("┌", "┬", "─", "┐", "│", "├", "┼", "┤", "└", "┴", "┘"))


_MKDOCS_THEME_VARIANTS = {"only-light", "only-dark"}


def _strip_mkdocs_theme_variant(src: str) -> str:
    """Drop MkDocs Material light/dark suffixes appended to image URLs."""
    base, sep, fragment = src.partition("#")
    if sep and fragment.lower() in _MKDOCS_THEME_VARIANTS:
        return base
    return src


def _is_bibliography_placeholder(text: str) -> bool:
    """Whether a footnote body just points readers to the bibliography."""
    normalised = text.strip().rstrip(".").strip().lower()
    return normalised in {"see bibliography", "see the bibliography"}


def _strip_text(text: str) -> str:
    """Collapse whitespace runs to a single space and strip — mirrors
    BeautifulSoup ``get_text(strip=True)`` on a single element's inline run.
    """
    return " ".join(text.split())


__all__ = ["LaTeXWriteError", "LaTeXWriter"]
