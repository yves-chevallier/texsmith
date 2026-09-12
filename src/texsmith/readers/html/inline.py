"""Inline lowerings: phrasing-level HTML tags into the generated inline models.

Each ``@reads(..., level=INLINE)`` callable turns one HTML tag into an inline
node (or sequence), recursing into children via ``ctx.lower_inline``. Semantic
concepts (emphasis, code, links, math, notes, index entries, …) map to the
typed nodes of :mod:`texsmith.ir.model`; anything the models do not express
(critic markup, helper links, ``data-script`` runs) maps to a
:class:`~texsmith.ir.model.SpanNode` carrying a ``role`` attribute, which the
writers render transparently.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from texsmith.extensions.texlogos.specs import iter_specs
from texsmith.ir import model

from ._helpers import classes, coerce_attr, make_attrs
from .registry import NotHandled, ReadLevel, reads


if TYPE_CHECKING:  # pragma: no cover - typing only
    from bs4.element import Tag

    from .context import ReadContext
    from .registry import _NotHandledType


# ---------------------------------------------------------------------------
# Simple emphasis-like wrappers (content recurses inline)
# ---------------------------------------------------------------------------


@reads("em", "i", level=ReadLevel.INLINE, name="emphasis")
def read_emphasis(tag: Tag, ctx: ReadContext) -> model.Emph:
    return model.Emph(content=ctx.lower_inline(tag.children))


@reads("strong", "b", level=ReadLevel.INLINE, name="strong")
def read_strong(tag: Tag, ctx: ReadContext) -> model.Strong:
    return model.Strong(content=ctx.lower_inline(tag.children))


@reads("sub", level=ReadLevel.INLINE, name="subscript")
def read_subscript(tag: Tag, ctx: ReadContext) -> model.Subscript:
    return model.Subscript(content=ctx.lower_inline(tag.children))


@reads("q", level=ReadLevel.INLINE, name="quoted")
def read_quoted(tag: Tag, ctx: ReadContext) -> model.Quoted:
    return model.Quoted(content=ctx.lower_inline(tag.children))


@reads("br", level=ReadLevel.INLINE, name="line_break")
def read_line_break(_tag: Tag, _ctx: ReadContext) -> model.LineBreak:
    return model.LineBreak()


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


def _role_span(role: str, content: tuple[model.Inline, ...], **extra: str) -> model.SpanNode:
    return model.SpanNode(attrs=make_attrs(kv={"role": role, **extra}), content=content)


@reads("del", "s", level=ReadLevel.INLINE, name="strikeout", priority=10)
def read_strikeout(tag: Tag, ctx: ReadContext) -> model.SpanNode | model.Strikeout:
    role = _critic_role(tag, "deletion")
    content = ctx.lower_inline(tag.children)
    return _role_span(role, content) if role else model.Strikeout(content=content)


@reads("ins", "u", level=ReadLevel.INLINE, name="underline", priority=10)
def read_underline(tag: Tag, ctx: ReadContext) -> model.SpanNode | model.Underline:
    role = _critic_role(tag, "addition")
    content = ctx.lower_inline(tag.children)
    return _role_span(role, content) if role else model.Underline(content=content)


@reads("mark", level=ReadLevel.INLINE, name="highlight", priority=10)
def read_highlight(tag: Tag, ctx: ReadContext) -> model.SpanNode | model.Highlight:
    role = _critic_role(tag, "highlight")
    content = ctx.lower_inline(tag.children)
    return _role_span(role, content) if role else model.Highlight(content=content)


# ---------------------------------------------------------------------------
# span: heavily overloaded — many semantic roles distinguished by class/attr
# ---------------------------------------------------------------------------


@reads("span", level=ReadLevel.INLINE, name="span", priority=0)
def read_span(
    tag: Tag, ctx: ReadContext
) -> model.Inline | tuple[model.Inline, ...] | _NotHandledType:
    """Lower the many flavours of ``<span>`` to typed nodes or a generic Span."""
    cls = classes(tag.get("class"))

    # Raw inline LaTeX payload (``{latex}[…]`` → ``<span class="latex-raw">``).
    if "latex-raw" in cls:
        return model.RawInline(format="latex", text=tag.get_text())

    # Inline math payload (mdx_math / arithmatex): keep the raw TeX source.
    if "arithmatex" in cls:
        return model.Math(text=_math_payload(tag.get_text()), display=False)

    # Small caps (texsmith SmallCaps extension).
    if "texsmith-smallcaps" in cls:
        return model.SmallCaps(content=ctx.lower_inline(tag.children))

    # Twemoji inline SVG span: carry the emoji token (title/text).
    if "twemoji" in cls:
        token = (coerce_attr(tag.get("title")) or tag.get_text(strip=True) or "").strip()
        return emoji_span(token)

    # Keystrokes: ``<span class="keys"><kbd class="key-ctrl">…`` (pymdownx.keys).
    if "keys" in cls:
        return model.Keystroke(keys=_keystroke_keys(tag))

    # Index entry: ``<span class="ts-hashtag|ts-index" data-tag…>``.
    if "ts-hashtag" in cls or "ts-index" in cls:
        entry = _index_entry(tag, ctx)
        return entry if entry is not None else NotHandled

    # Index entry (inline variant): ``<span data-tag-name="a, b" data-tag-style>``
    # — the comma-separated nested form the inline index handler used.
    if coerce_attr(tag.get("data-tag-name")):
        entry = _index_entry_named(tag, ctx)
        return entry if entry is not None else NotHandled

    # TeX logo: ``<span class="tex-logo" data-tex-logo="latex">``. The word
    # stays a ``Str``; the writers' ``typography.tex-logos`` feature sets it.
    if "tex-logo" in cls:
        slug = coerce_attr(tag.get("data-tex-logo")) or ""
        return model.Str(_TEX_LOGO_WORDS.get(slug, tag.get_text(strip=True) or slug))

    # latex-text span — the {LaTeX} helper.
    if "latex-text" in cls:
        return model.Str("LaTeX")

    # Critic substitution: paired <del>/<ins> inside the span.
    if "critic" in cls and "subst" in cls:
        return _role_span("critic-substitution", ctx.lower_inline(tag.children))
    if "critic" in cls and "comment" in cls:
        return _role_span("critic-comment", ctx.lower_inline(tag.children))

    # MkDocs autoref placeholder.
    identifier = coerce_attr(tag.get("data-autorefs-identifier"))
    if identifier:
        return model.Link(target=model.Anchor(identifier), content=ctx.lower_inline(tag.children))

    # data-script font wrapper (e.g. a phonetic / script run).
    slug = coerce_attr(tag.get("data-script"))
    if slug:
        return model.SpanNode(
            attrs=make_attrs(kv={"script": slug}), content=ctx.lower_inline(tag.children)
        )

    # Custom counter marker: the printed number doubles as a label target.
    if "ts-counter" in cls:
        return _counter_item(tag)

    # A span carrying an id or classes is a host for them; a bare span is
    # transparent — its children stand in its place.
    span_id = coerce_attr(tag.get("id"))
    content = ctx.lower_inline(tag.children)
    if span_id or cls:
        return model.SpanNode(attrs=make_attrs(id=span_id, classes=cls), content=content)
    return content


#: ``data-tex-logo`` slug → the word tmark's ``TEX_LOGOS`` registry sets as a logo.
_TEX_LOGO_WORDS: dict[str, str] = {spec.slug: spec.aliases[0] for spec in iter_specs()}


def emoji_span(token: str) -> model.SpanNode:
    """An emoji (twemoji / emojione markup): ``Span{emoji=…}`` around the character."""
    return model.SpanNode(attrs=make_attrs(kv={"emoji": token}), content=(model.Str(token),))


def _counter_item(tag: Tag) -> model.CounterItem | tuple[model.Inline, ...]:
    """``<span class="ts-counter" data-counter="fw" data-key="x">`` → ``CounterItem``."""
    prefix = (coerce_attr(tag.get("data-counter")) or "").strip()
    key = (coerce_attr(tag.get("data-key")) or "").strip()
    if not (prefix and key):
        identifier = coerce_attr(tag.get("id")) or ""
        prefix, _, key = identifier.partition(":")
    if prefix and key:
        return model.CounterItem(key=key, prefix=prefix)
    text = tag.get_text()
    return (model.Str(text),) if text else ()


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


def _index_entry(tag: Tag, ctx: ReadContext) -> tuple[model.Inline, ...] | None:
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
    return _index_nodes(tag, ctx, path, coerce_attr(tag.get("data-style")))


def _index_entry_named(tag: Tag, ctx: ReadContext) -> tuple[model.Inline, ...] | None:
    """Lower the ``data-tag-name`` index span (comma-separated nested path)."""
    raw = coerce_attr(tag.get("data-tag-name")) or ""
    path = [segment.strip() for segment in raw.split(",") if segment.strip()]
    if not path:
        return None
    return _index_nodes(tag, ctx, path, coerce_attr(tag.get("data-tag-style")))


def _index_nodes(
    tag: Tag, ctx: ReadContext, path: list[str], style: str | None
) -> tuple[model.Inline, ...]:
    """The visible text of an index span, then the zero-width ``IndexEntry``.

    The legacy ``{b}`` suffix (a bold page number) is ``main=true``; the
    ``{i}`` style has no model counterpart and is dropped (spec Appendix
    "Deprecation schedule").
    """
    registry = (coerce_attr(tag.get("data-registry")) or "").strip() or None
    main = "b" in (style or "").strip().lower()
    entry = model.IndexEntry(
        main=main,
        path=tuple((model.Str(segment),) for segment in path),
        registry=registry,
    )
    return (*ctx.lower_inline(tag.children), entry)


# ---------------------------------------------------------------------------
# Code spans
# ---------------------------------------------------------------------------


@reads("code", level=ReadLevel.INLINE, name="inline_code")
def read_inline_code(tag: Tag, _ctx: ReadContext) -> model.Code:
    cls = classes(tag.get("class"))
    lang = next((c[len("language-") :] for c in cls if c.startswith("language-")), None)
    return model.Code(text=_code_text(tag), lang=lang or None)


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


def link_target(href: str) -> model.Target:
    """``#id`` is an anchor of this document; anything else a URL."""
    if href.startswith("#"):
        return model.Anchor(href[1:])
    return model.Url(href)


@reads("a", level=ReadLevel.INLINE, name="link", priority=0)
def read_link(
    tag: Tag, ctx: ReadContext
) -> model.Inline | tuple[model.Inline, ...] | None | _NotHandledType:
    cls = classes(tag.get("class"))

    # Index annotation carried on an anchor (``<a data-tag-name=…>``).
    if coerce_attr(tag.get("data-tag-name")):
        entry = _index_entry_named(tag, ctx)
        if entry is not None:
            return entry

    # Navigational chrome (footnote markers/back-refs, header anchors,
    # lightbox wrappers) is dropped. A footnote *marker* is carried by the
    # enclosing ``<sup id>`` (a ``Note``); a back-ref is pure chrome.
    if _CHROME_ANCHOR_CLASSES.intersection(cls):
        return None
    if "glightbox" in cls:
        return ctx.lower_inline(tag.children)

    # Unicode helper link: ``<a class="ycr-unicode" href=…>CODE</a>``.
    if "ycr-unicode" in cls:
        code = tag.get_text(strip=True)
        href = coerce_attr(tag.get("href")) or ""
        return model.Link(target=link_target(href), content=(model.Str(f"U+{code}"),))
    # Regex helper link.
    if "ycr-regex" in cls:
        href = coerce_attr(tag.get("href")) or ""
        return _role_span("regex", ctx.lower_inline(tag.children), href=href)

    href = coerce_attr(tag.get("href"))
    title = coerce_attr(tag.get("title")) or None
    content = ctx.lower_inline(tag.children)

    if not href:
        identifier = coerce_attr(tag.get("id"))
        if identifier:
            # An anchor that only defines a label.
            return model.SpanNode(attrs=make_attrs(id=identifier), content=content)
        # Anchor with no destination: keep its content transparently.
        return content

    return model.Link(target=link_target(href), content=content, title=title)


@reads("autoref", level=ReadLevel.INLINE, name="autoref")
def read_autoref(tag: Tag, ctx: ReadContext) -> model.Link:
    identifier = coerce_attr(tag.get("identifier")) or ""
    return model.Link(target=model.Anchor(identifier), content=ctx.lower_inline(tag.children))


# ---------------------------------------------------------------------------
# Images / math script / abbr / footnote refs
# ---------------------------------------------------------------------------


@reads("img", level=ReadLevel.ANY, name="image")
def read_image(tag: Tag, ctx: ReadContext) -> model.Inline:
    cls = classes(tag.get("class"))
    # Twemoji / emoji images carry their token in alt/title/data-emoji.
    if {"twemoji", "emojione"}.intersection(cls):
        token = (
            coerce_attr(tag.get("alt"))
            or coerce_attr(tag.get("data-emoji"))
            or coerce_attr(tag.get("title"))
            or ""
        )
        return emoji_span(token)
    return model.Image(
        src=coerce_attr(tag.get("src")) or "",
        alt=alt_inlines(coerce_attr(tag.get("alt")) or "", ctx),
        attrs=make_attrs(
            id=coerce_attr(tag.get("id")),
            kv={
                "width": coerce_attr(tag.get("width")),
                "title": coerce_attr(tag.get("title")),
                **_render_options(tag),
            },
        ),
    )


#: ``attr_list`` keys an image may carry for the converter that renders it
#: (``![alt](diagram.drawio){crop=false}``). Anything else on the ``<img>``
#: stays an HTML attribute the IR ignores.
_RENDER_OPTION_ATTRS: tuple[str, ...] = ("crop",)


def _render_options(tag: Tag) -> dict[str, str]:
    """Collect the converter options an ``attr_list`` block set on the image."""
    collected: dict[str, str] = {}
    for name in _RENDER_OPTION_ATTRS:
        value = coerce_attr(tag.get(name))
        if value:
            collected[name] = value
    return collected


#: Characters that can start inline Markdown syntax; an alt without any of
#: them is plain text and skips the re-parse.
_ALT_MARKUP_RE = re.compile(r"[*_`\[<]")

_ALT_PARSER = None


def alt_inlines(alt: str, _ctx: ReadContext) -> tuple[model.Inline, ...]:
    """Lower an ``alt`` attribute, parsing the inline markup it carries.

    A Markdown renderer copies the image description verbatim into ``alt``, so
    ``![anti-*windup*](x.png)`` reaches the HTML with its asterisks intact.
    The alt doubles as the figure caption (and as its short caption), where
    the emphasis the author wrote must not ship as literal punctuation — so the
    text goes back through ``tmark.parse``, the parser the rest of the pipeline
    uses, and its first paragraph's inlines are the answer.
    """
    if not alt:
        return ()
    if not _ALT_MARKUP_RE.search(alt):
        return (model.Str(alt),)

    from texsmith.readers.tmark import read

    document, _diagnostics = read(alt, name="<alt>")
    for block in document.blocks:
        if isinstance(block, model.Para):
            return tuple(block.content)
    return (model.Str(alt),)


@reads("script", level=ReadLevel.ANY, name="math_script")
def read_math_script(tag: Tag, _ctx: ReadContext) -> model.Math | _NotHandledType:
    type_attr = coerce_attr(tag.get("type")) or ""
    if not type_attr.startswith("math/tex"):
        return NotHandled
    display = "mode=display" in type_attr
    return model.Math(text=tag.get_text().strip(), display=display)


@reads("texsmith-missing-footnote", level=ReadLevel.INLINE, name="missing_footnote")
def read_missing_footnote(tag: Tag, _ctx: ReadContext) -> model.Ref:
    """A ``[^key]`` reference with no footnote body: a citation, resolved downstream.

    The ``missing_footnotes`` extension emits this placeholder for references
    the footnote extension could not pair; ``tmark.resolve`` decides between a
    label, a bibliography key and a glossary entry (spec §Ref).
    """
    key = (coerce_attr(tag.get("data-footnote-id")) or tag.get_text(strip=True)).strip()
    return model.Ref(bracketed=True, items=(model.RefItem(key=key),))


@reads("abbr", level=ReadLevel.INLINE, name="abbreviation")
def read_abbr(tag: Tag, ctx: ReadContext) -> model.Inline | tuple[model.Inline, ...]:
    title = (coerce_attr(tag.get("title")) or "").strip()
    text = tag.get_text()
    if not (title and text.strip()):
        # No expansion: behaves as plain text.
        return ctx.lower_inline(tag.children)
    ctx.define_abbreviation(text, title)
    return model.Abbr(text=text)


_FOOTNOTE_REF_ID = re.compile(r"^fnref\d*:(?P<label>.+)$")


@reads("sup", level=ReadLevel.INLINE, name="superscript", priority=0)
def read_superscript(tag: Tag, ctx: ReadContext) -> model.Inline:
    identifier = coerce_attr(tag.get("id")) or ""
    match = _FOOTNOTE_REF_ID.match(identifier)
    if match is not None:
        # Footnote reference marker (``<sup id="fnref:label">``); the body is
        # registered on the document by the block-level footnote lowering.
        return model.Note(label=footnote_label(match.group("label")))
    return model.Superscript(content=ctx.lower_inline(tag.children))


def footnote_label(raw: str) -> str:
    """The author's ``[^label]`` behind Python-Markdown's ``fn:label`` ids.

    A label reused across documents of one build gets a ``-N`` suffix in the
    HTML; the definition and its references share it, so it is kept.
    """
    return raw.strip()


__all__ = [
    "alt_inlines",
    "emoji_span",
    "footnote_label",
    "link_target",
    "read_abbr",
    "read_autoref",
    "read_emphasis",
    "read_highlight",
    "read_image",
    "read_inline_code",
    "read_line_break",
    "read_link",
    "read_math_script",
    "read_missing_footnote",
    "read_quoted",
    "read_span",
    "read_strikeout",
    "read_strong",
    "read_subscript",
    "read_superscript",
    "read_underline",
]
