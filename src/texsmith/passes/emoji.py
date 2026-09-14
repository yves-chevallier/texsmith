"""The ``emoji`` pass: emoji clusters in text → ``Span{emoji}`` or an icon ``Image``.

``writers-and-passes.md`` §3 row 8; ports ``LaTeXWriter._emoji_renderer`` /
``_render_emoji_span`` and the ``escaper.py`` segmentation. Runs before
``scripts`` so a cluster is never classified as a script run.

Every grapheme cluster the ``emoji`` library recognises inside a
:class:`~tmark.ir.model.Str` (code, math and raw nodes hold no ``Str``)
becomes, per the resolved ``fonts.emoji`` mode:

* **font modes** (``black``, ``color``, ``symbola``, ``twemoji``, a custom
  family — the default is ``black``): ``Span{attrs: emoji=<cluster>}`` whose
  content is the cluster; the LaTeX writer renders ``\\tsemoji{…}`` and
  names ``ts-fonts``;
* **artifact**: the Twemoji SVG is fetched through the ``fetch-image``
  strategy (converted to PDF, as the legacy renderer did) and the cluster
  becomes ``Image{src=assets/…, .icon}``, the ``\\tsicon`` contract; when the
  fetch fails the character stays as text and ``asset-missing`` is emitted.

The mode is read as ``_build_runtime_common`` read it — ``emoji``,
``fonts.emoji``, ``press.emoji``, ``press.fonts.emoji`` of the template
overrides, then of the front matter — and, when explicit, handed back as
``ctx.values["emoji_mode"]`` so the pipeline sets the ``emoji`` template
override the ``ts-fonts`` provisioning reads. Derived nodes take the
``Str``'s span and fresh ids (span rule 2).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import emoji as _emoji
from tmark.ir import model
from tmark.ir.walk import map_inlines

from texsmith.core.conversion.settings import extract_emoji_mode
from texsmith.core.exceptions import exception_hint
from texsmith.passes import PassContext, spec
from texsmith.passes.assets import asset_registry


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["ARTIFACT_MODE", "DEFAULT_MODE", "resolve_emoji_mode", "run", "twemoji_url"]

DEFAULT_MODE = "black"
ARTIFACT_MODE = "artifact"
_TWEMOJI_BASE = "https://twemoji.maxcdn.com/v/latest/svg/"


def twemoji_url(cluster: str) -> str:
    """The Twemoji SVG URL of a cluster (``writer.py:225``)."""
    return _TWEMOJI_BASE + "-".join(f"{ord(char):x}" for char in cluster) + ".svg"


def resolve_emoji_mode(ctx: PassContext) -> str | None:
    """The explicit ``fonts.emoji`` mode of the first context that sets one."""
    for context in ctx.contexts:
        mode = extract_emoji_mode(context)
        if mode:
            return mode
    return None


def _is_fenced(node: model.Node) -> bool:
    """A span the pass or the ``scripts`` pass already produced."""
    if not isinstance(node, model.SpanNode):
        return False
    return any(key in {"emoji", "script"} for key, _ in node.attrs.kv)


@spec("emoji", after=("assets",), stage="pre", needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    if document.ir is None:
        return document
    explicit = resolve_emoji_mode(ctx)
    if explicit:
        ctx.values["emoji_mode"] = explicit
    mode = explicit or DEFAULT_MODE
    registry = asset_registry(ctx) if mode == ARTIFACT_MODE else None
    request = ctx.request
    user_agent = getattr(request, "http_user_agent", None)

    def artifact(node: model.Str, cluster: str) -> model.Inline:
        from texsmith.adapters.transformers import fetch_image

        assert registry is not None
        url = twemoji_url(cluster)
        stored = registry.lookup(url)
        if stored is None:
            options = {"emitter": ctx.emitter}
            if isinstance(user_agent, str) and user_agent.strip():
                options["user_agent"] = user_agent.strip()
            try:
                artefact = fetch_image(url, output_dir=registry.output_root, **options)
            except Exception as exc:
                ctx.diagnostics.emit(
                    "asset-missing",
                    node.span,
                    f"emoji artifact for '{cluster}' could not be fetched "
                    f"({exception_hint(exc) or exc}); the character is kept as text",
                )
                return model.Str(text=cluster, id=ctx.ids.next(), span=node.span)
            stored = registry.register(url, artefact)
        return model.Image(
            src=registry.latex_path(stored),
            attrs=model.Attrs(classes=("icon",)),
            id=ctx.ids.next(),
            span=node.span,
        )

    def span(node: model.Str, cluster: str) -> model.Inline:
        return model.SpanNode(
            attrs=model.Attrs(kv=(("emoji", cluster),)),
            content=(model.Str(text=cluster, id=ctx.ids.next(), span=node.span),),
            id=ctx.ids.next(),
            span=node.span,
        )

    render = artifact if mode == ARTIFACT_MODE else span

    def visit(node: model.Inline) -> model.Inline | tuple[model.Inline, ...]:
        if not isinstance(node, model.Str) or node.text.isascii():
            return node
        entries = _emoji.emoji_list(node.text)
        if not entries:
            return node
        text = node.text
        pieces: list[model.Inline] = []
        cursor = 0
        for entry in entries:
            start, end = entry["match_start"], entry["match_end"]
            if start > cursor:
                pieces.append(replace(node, text=text[cursor:start], id=ctx.ids.next()))
            pieces.append(render(node, text[start:end]))
            cursor = end
        if cursor < len(text):
            pieces.append(replace(node, text=text[cursor:], id=ctx.ids.next()))
        return tuple(pieces)

    rebuilt = map_inlines(document.ir, visit, skip=_is_fenced)
    if rebuilt is document.ir:
        return document
    return document.evolve(ir=rebuilt)
