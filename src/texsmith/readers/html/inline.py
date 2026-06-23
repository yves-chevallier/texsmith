"""Inline lowerings: phrasing-level HTML tags into inline IR.

Each ``@reads(..., level=INLINE)`` callable turns one HTML tag into an inline
IR node (or sequence), recursing into children via ``ctx.lower_inline``. No
LaTeX is produced; semantic concepts (emphasis, code, links, math, …) map to
typed inline nodes, and anything genuinely generic (critic markup, helper
links, ``data-script`` spans, abbreviations) maps to a :class:`~texsmith.ir.Span`
carrying a ``role`` attribute hint, per the IR contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from texsmith.ir import nodes as ir

from ._helpers import attrs_tuple, classes, coerce_attr
from .registry import NotHandled, ReadLevel, reads


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from .context import ReadContext
    from .registry import _NotHandledType


# ---------------------------------------------------------------------------
# Simple emphasis-like wrappers (content recurses inline)
# ---------------------------------------------------------------------------


@reads("em", "i", level=ReadLevel.INLINE, name="emphasis")
def read_emphasis(tag: Tag, ctx: ReadContext) -> ir.Emph:
    return ir.Emph(content=ctx.lower_inline(tag.children))


@reads("strong", "b", level=ReadLevel.INLINE, name="strong")
def read_strong(tag: Tag, ctx: ReadContext) -> ir.Strong:
    return ir.Strong(content=ctx.lower_inline(tag.children))


@reads("sub", level=ReadLevel.INLINE, name="subscript")
def read_subscript(tag: Tag, ctx: ReadContext) -> ir.Subscript:
    return ir.Subscript(content=ctx.lower_inline(tag.children))


@reads("q", level=ReadLevel.INLINE, name="quoted")
def read_quoted(tag: Tag, ctx: ReadContext) -> ir.Quoted:
    return ir.Quoted(content=ctx.lower_inline(tag.children))


@reads("br", level=ReadLevel.INLINE, name="line_break")
def read_line_break(_tag: Tag, _ctx: ReadContext) -> ir.LineBreak:
    return ir.LineBreak()


# ---------------------------------------------------------------------------
# del / ins / mark carry an optional ``critic`` review semantic
# ---------------------------------------------------------------------------


def _critic_role(tag: Tag, default: str) -> str:
    """Map a ``pymdownx.critic`` class set to a span ``role``."""
    cls = classes(tag.get("class"))
    if "critic" not in cls:
        return ""
    if "comment" in cls:
        return "critic-comment"
    return f"critic-{default}"


@reads("del", "s", level=ReadLevel.INLINE, name="strikeout", priority=10)
def read_strikeout(tag: Tag, ctx: ReadContext) -> ir.Span | ir.Strikeout:
    role = _critic_role(tag, "deletion")
    content = ctx.lower_inline(tag.children)
    if role:
        return ir.Span(content=content, attrs=attrs_tuple({"role": role}))
    return ir.Strikeout(content=content)


@reads("ins", "u", level=ReadLevel.INLINE, name="underline", priority=10)
def read_underline(tag: Tag, ctx: ReadContext) -> ir.Span | ir.Underline:
    role = _critic_role(tag, "addition")
    content = ctx.lower_inline(tag.children)
    if role:
        return ir.Span(content=content, attrs=attrs_tuple({"role": role}))
    return ir.Underline(content=content)


@reads("mark", level=ReadLevel.INLINE, name="highlight", priority=10)
def read_highlight(tag: Tag, ctx: ReadContext) -> ir.Span | ir.Highlight:
    role = _critic_role(tag, "highlight")
    content = ctx.lower_inline(tag.children)
    if role:
        return ir.Span(content=content, attrs=attrs_tuple({"role": role}))
    return ir.Highlight(content=content)


# ---------------------------------------------------------------------------
# span: heavily overloaded — many semantic roles distinguished by class/attr
# ---------------------------------------------------------------------------


@reads("span", level=ReadLevel.INLINE, name="span", priority=0)
def read_span(tag: Tag, ctx: ReadContext) -> ir.Inline | _NotHandledType:
    """Lower the many flavours of ``<span>`` to typed nodes or a generic Span."""
    cls = classes(tag.get("class"))

    # Raw inline LaTeX payload (``{latex}[…]`` → ``<span class="latex-raw">``).
    if "latex-raw" in cls:
        return ir.RawInline(format="latex", text=tag.get_text())

    # Inline math payload (mdx_math / arithmatex): keep the raw TeX source.
    if "arithmatex" in cls:
        return ir.Math(text=_math_payload(tag.get_text()), display=False)

    # Small caps (texsmith SmallCaps extension).
    if "texsmith-smallcaps" in cls:
        return ir.SmallCaps(content=ctx.lower_inline(tag.children))

    # Twemoji inline SVG span: carry the emoji token (title/text).
    if "twemoji" in cls:
        token = (coerce_attr(tag.get("title")) or tag.get_text(strip=True) or "").strip()
        return ir.Span(content=(ir.Str(token),), attrs=attrs_tuple({"role": "emoji"}))

    # Keystrokes: ``<span class="keys"><kbd class="key-ctrl">…`` (pymdownx.keys).
    if "keys" in cls:
        return ir.Keystroke(keys=_keystroke_keys(tag))

    # Index entry: ``<span class="ts-hashtag|ts-index" data-tag…>``.
    if "ts-hashtag" in cls or "ts-index" in cls:
        entry = _index_entry(tag, ctx)
        return entry if entry is not None else NotHandled

    # Index entry (inline variant): ``<span data-tag-name="a, b" data-tag-style>``
    # — the comma-separated nested form the legacy inline index handler used.
    if coerce_attr(tag.get("data-tag-name")):
        entry = _index_entry_named(tag, ctx)
        return entry if entry is not None else NotHandled

    # TeX logo: ``<span class="tex-logo" data-tex-logo="latex">``.
    if "tex-logo" in cls:
        slug = coerce_attr(tag.get("data-tex-logo")) or ""
        return ir.TexLogo(name=slug or tag.get_text(strip=True))

    # latex-text span — the {LaTeX} helper.
    if "latex-text" in cls:
        return ir.TexLogo(name="latex")

    # Critic substitution: paired <del>/<ins> inside the span.
    if "critic" in cls and "subst" in cls:
        return ir.Span(
            content=ctx.lower_inline(tag.children),
            attrs=attrs_tuple({"role": "critic-substitution"}),
        )
    if "critic" in cls and "comment" in cls:
        return ir.Span(
            content=ctx.lower_inline(tag.children),
            attrs=attrs_tuple({"role": "critic-comment"}),
        )

    # MkDocs autoref placeholder.
    identifier = coerce_attr(tag.get("data-autorefs-identifier"))
    if identifier:
        return ir.Link(content=ctx.lower_inline(tag.children), target=f"#{identifier}")

    # data-script font wrapper (e.g. a phonetic / script run).
    slug = coerce_attr(tag.get("data-script"))
    if slug:
        return ir.Span(
            content=ctx.lower_inline(tag.children),
            attrs=attrs_tuple({"role": "script", "script": slug}),
        )

    # Plain span with classes: keep them as a generic Span hint.
    if cls:
        return ir.Span(
            content=ctx.lower_inline(tag.children),
            attrs=attrs_tuple({"class": " ".join(cls)}),
        )

    # Bare span: transparent — lower to its children directly.
    return ir.Span(content=ctx.lower_inline(tag.children))


def _math_payload(text: str) -> str:
    """Strip the math delimiters arithmatex leaves in the text node."""
    stripped = text.strip()
    pairs = (("$$", "$$"), (r"\[", r"\]"), (r"\(", r"\)"), ("$", "$"))
    for opening, closing in pairs:
        if (
            stripped.startswith(opening)
            and stripped.endswith(closing)
            and len(stripped) >= len(opening) + len(closing)
        ):
            return stripped[len(opening) : len(stripped) - len(closing)].strip()
    return stripped


def _keystroke_keys(tag: Tag) -> tuple[str, ...]:
    keys: list[str] = []
    for kbd in tag.find_all("kbd"):
        kbd_classes = classes(kbd.get("class"))
        token = next((c[4:] for c in kbd_classes if c.startswith("key-")), None)
        keys.append(token or kbd.get_text(strip=True))
    return tuple(keys)


def _index_entry(tag: Tag, ctx: ReadContext) -> ir.IndexEntry | None:
    path: list[str] = []
    index = 0
    while True:
        key = "data-tag" if index == 0 else f"data-tag{index}"
        value = coerce_attr(tag.get(key))
        if not value:
            break
        cleaned = value.strip()
        if cleaned:
            path.append(cleaned)
        index += 1
    if not path:
        return None
    style = (coerce_attr(tag.get("data-style")) or "").strip().lower()
    if style == "ib":
        style = "bi"
    if style not in {"b", "i", "bi"}:
        style = ""
    registry = (coerce_attr(tag.get("data-registry")) or "").strip()
    visible = ctx.lower_inline(tag.children)
    return ir.IndexEntry(
        path=tuple(path),
        style=style,
        registry=registry,
        visible=visible,
    )


def _index_entry_named(tag: Tag, ctx: ReadContext) -> ir.IndexEntry | None:
    """Lower the ``data-tag-name`` index span (comma-separated nested path)."""
    raw = coerce_attr(tag.get("data-tag-name")) or ""
    path = [segment.strip() for segment in raw.split(",") if segment.strip()]
    if not path:
        return None
    style = (coerce_attr(tag.get("data-tag-style")) or "").strip().lower()
    if style == "ib":
        style = "bi"
    if style not in {"b", "i", "bi"}:
        style = ""
    registry = (coerce_attr(tag.get("data-registry")) or "").strip()
    visible = ctx.lower_inline(tag.children)
    return ir.IndexEntry(path=tuple(path), style=style, registry=registry, visible=visible)


# ---------------------------------------------------------------------------
# Code spans
# ---------------------------------------------------------------------------


@reads("code", level=ReadLevel.INLINE, name="inline_code")
def read_inline_code(tag: Tag, _ctx: ReadContext) -> ir.Code:
    cls = classes(tag.get("class"))
    lang = next(
        (c[len("language-") :] for c in cls if c.startswith("language-")),
        "",
    )
    if not lang and "highlight" in cls:
        lang = "text"
    text = _code_text(tag)
    return ir.Code(text=text, lang=lang)


def _code_text(tag: Tag) -> str:
    cls = classes(tag.get("class"))
    if any(c.startswith("language-") for c in cls) or "highlight" in cls:
        spans = tag.find_all("span")
        if spans:
            return "".join(span.get_text() for span in spans)
    return tag.get_text()


# ---------------------------------------------------------------------------
# Links / references
# ---------------------------------------------------------------------------


_CHROME_ANCHOR_CLASSES = frozenset({"headerlink", "footnote-ref", "footnote-backref"})


@reads("a", level=ReadLevel.INLINE, name="link", priority=0)
def read_link(tag: Tag, ctx: ReadContext) -> ir.Inline | None | _NotHandledType:
    cls = classes(tag.get("class"))

    # Index annotation carried on an anchor (``<a data-tag-name=…>``).
    if coerce_attr(tag.get("data-tag-name")):
        entry = _index_entry_named(tag, ctx)
        if entry is not None:
            return entry

    # Navigational chrome (footnote markers/back-refs, header anchors,
    # lightbox wrappers) is dropped, mirroring the legacy ``discard_unwanted``
    # PRE strip rules. A footnote *marker* is carried by the enclosing
    # ``<sup id>`` (a footnote-ref span); a back-ref is pure chrome.
    if _CHROME_ANCHOR_CLASSES.intersection(cls):
        if "footnote-ref" in cls:
            # Keep the visible marker text so the footnote-ref span still has a
            # fallback rendering when no body/citation resolves.
            content = ctx.lower_inline(tag.children)
            return ir.Span(content=content) if content else None
        return None
    if "glightbox" in cls:
        content = ctx.lower_inline(tag.children)
        return ir.Span(content=content) if content else None

    # Unicode helper link: ``<a class="ycr-unicode" href=…>CODE</a>``.
    if "ycr-unicode" in cls:
        code = tag.get_text(strip=True)
        href = coerce_attr(tag.get("href")) or ""
        return ir.Link(
            content=(ir.Str(f"U+{code}"),),
            target=href,
            title="",
        )
    # Regex helper link.
    if "ycr-regex" in cls:
        href = coerce_attr(tag.get("href")) or ""
        return ir.Span(
            content=ctx.lower_inline(tag.children),
            attrs=attrs_tuple({"role": "regex", "href": href}),
        )

    href = coerce_attr(tag.get("href"))
    title = coerce_attr(tag.get("title")) or ""
    content = ctx.lower_inline(tag.children)

    if href is None or href == "":
        identifier = coerce_attr(tag.get("id"))
        if identifier:
            # An anchor that only defines a label.
            return ir.Span(
                content=content,
                attrs=attrs_tuple({"role": "label", "id": identifier}),
            )
        # Anchor with no destination: keep its content transparently.
        return ir.Span(content=content) if content else None

    return ir.Link(content=content, target=href, title=title)


@reads("autoref", level=ReadLevel.INLINE, name="autoref")
def read_autoref(tag: Tag, ctx: ReadContext) -> ir.Link:
    identifier = coerce_attr(tag.get("identifier")) or ""
    return ir.Link(content=ctx.lower_inline(tag.children), target=f"#{identifier}")


# ---------------------------------------------------------------------------
# Images / math script / abbr / footnote refs
# ---------------------------------------------------------------------------


@reads("img", level=ReadLevel.ANY, name="image")
def read_image(tag: Tag, _ctx: ReadContext) -> ir.Inline:
    cls = classes(tag.get("class"))
    # Twemoji / emoji images carry their token in alt/title/data-emoji.
    if {"twemoji", "emojione"}.intersection(cls):
        token = (
            coerce_attr(tag.get("alt"))
            or coerce_attr(tag.get("data-emoji"))
            or coerce_attr(tag.get("title"))
            or ""
        )
        return ir.Span(content=(ir.Str(token),), attrs=attrs_tuple({"role": "emoji"}))
    return ir.Image(
        src=coerce_attr(tag.get("src")) or "",
        alt=(ir.Str(coerce_attr(tag.get("alt")) or ""),) if coerce_attr(tag.get("alt")) else (),
        title=coerce_attr(tag.get("title")) or "",
        width=coerce_attr(tag.get("width")) or "",
    )


@reads("script", level=ReadLevel.ANY, name="math_script")
def read_math_script(tag: Tag, _ctx: ReadContext) -> ir.Math | _NotHandledType:
    type_attr = coerce_attr(tag.get("type")) or ""
    if not type_attr.startswith("math/tex"):
        return NotHandled
    display = "mode=display" in type_attr
    return ir.Math(text=tag.get_text().strip(), display=display)


@reads("texsmith-missing-footnote", level=ReadLevel.INLINE, name="missing_footnote")
def read_missing_footnote(tag: Tag, ctx: ReadContext) -> ir.Span:
    """A reference whose footnote/citation body is resolved by the writer.

    The ``missing_footnotes`` extension emits this placeholder for ``[^id]``
    references with no inline definition; it may resolve to a footnote or a
    bibliography citation downstream. The reader records the identifier as a
    ``footnote-ref`` role and lets the writer (which owns the footnote / bib
    registries) decide.
    """
    identifier = (coerce_attr(tag.get("data-footnote-id")) or tag.get_text(strip=True)).strip()
    return ir.Span(
        content=ctx.lower_inline(tag.children),
        attrs=attrs_tuple({"role": "footnote-ref", "ref": identifier}),
    )


@reads("abbr", level=ReadLevel.INLINE, name="abbreviation")
def read_abbr(tag: Tag, ctx: ReadContext) -> ir.Inline:
    title = (coerce_attr(tag.get("title")) or "").strip()
    content = ctx.lower_inline(tag.children)
    if not title:
        # No expansion: behaves as plain text.
        return ir.Span(content=content) if content else ir.Str("")
    return ir.Span(content=content, attrs=attrs_tuple({"role": "abbr", "title": title}))


@reads("sup", level=ReadLevel.INLINE, name="superscript", priority=0)
def read_superscript(tag: Tag, ctx: ReadContext) -> ir.Inline:
    identifier = coerce_attr(tag.get("id"))
    if identifier:
        # Footnote reference marker (``<sup id="fnref:…">``); the footnote body
        # is matched and carried by the block-level footnote lowering, so the
        # reference site is recorded as a footnote-ref span hint.
        ref = identifier
        return ir.Span(
            content=ctx.lower_inline(tag.children),
            attrs=attrs_tuple({"role": "footnote-ref", "ref": ref}),
        )
    return ir.Superscript(content=ctx.lower_inline(tag.children))


__all__ = [
    "read_abbr",
    "read_autoref",
    "read_emphasis",
    "read_highlight",
    "read_image",
    "read_inline_code",
    "read_line_break",
    "read_link",
    "read_math_script",
    "read_quoted",
    "read_span",
    "read_strikeout",
    "read_strong",
    "read_subscript",
    "read_superscript",
    "read_underline",
]
