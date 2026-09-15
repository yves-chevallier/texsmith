"""The ``assets`` pass: every ``Image`` gets a real, output-relative ``src``.

``writers-and-passes.md`` §3 row 7 and open point (f): the pass owns copying,
conversion and fetching; the writer's ``Requires.assets`` is afterwards only
the list of what it included. Runs after ``include`` (sources are rebased to
the document's directory) and ``snippet``; independent of ``resolve``.

For each :class:`~tmark.ir.model.Image`:

* a **generated** diagram (``Image{src="", generate=mermaid, code=…}`` from a
  ```` ```mermaid ```` fence, a ``.mmd``/``.mermaid`` file, a ``mermaid.live``
  share URL) is rendered through the ``mermaid`` strategy — PDF for LaTeX,
  PNG for Typst as ``writers/typst/diagrams.py`` did — with the diagram
  backend of the request; a ``%% caption`` first line becomes a
  :class:`~tmark.ir.model.Caption` after the paragraph when no caption
  block sits next to it (``media.py:85``);
* a **remote** URL is fetched through the ``fetch-image`` strategy with the
  ``remote-assets.json`` manifest of ``writers/latex/assets.py``;
* a **local** file is copied, or converted by suffix (``.svg``/``.drawio``
  always, ``.png``/``.jpg`` under ``--convert-assets``, ``.pdf`` never) with
  the legacy helpers, so the naming (relative path kept, sha256 under
  ``--hash-assets`` or on a conflict), the ``.converted`` cache and the
  ``crop`` option of draw.io exports are the same; the Typst backend keeps
  the file as is except diagrams, which become PNG.

``src`` is rewritten to the path relative to the output directory
(``assets/…``). ``copy_assets=False`` substitutes the ``Str`` placeholder the
legacy writer emitted (the alt text, else ``[image]``; the caption, else
``Mermaid diagram`` for a diagram). A missing file emits ``asset-missing``, a
failed conversion or fetch ``asset-convert-failed``, both at the node's span,
and the node becomes a visible literal — never an exception. The copied
assets are handed back as ``ctx.values["assets"]`` (key → path).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from tmark.ir import model
from tmark.ir.walk import iter_child_fields, map_tree

from texsmith.adapters.transformers.mermaid_detect import (
    MERMAID_FILE_SUFFIXES,
    extract_mermaid_live_diagram,
    looks_like_mermaid,
)
from texsmith.core.context import AssetRegistry
from texsmith.core.exceptions import exception_hint
from texsmith.passes import PassContext, spec
from texsmith.passes.var import MISSING, lookup
from texsmith.writers.latex.assets import AssetOptions


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.documents import Document


__all__ = ["ASSETS_DIR", "asset_registry", "mermaid_caption", "run"]

#: The directory next to the output where assets are copied (``LaTeXRenderer.assets_root``).
ASSETS_DIR = "assets"
_THEME_VARIANTS = ("#only-light", "#only-dark")
_DRAWIO_SUFFIXES = {".drawio", ".dio"}
_REMOTE_SCHEMES = {"http", "https"}


def asset_registry(ctx: PassContext) -> AssetRegistry:
    """The asset registry of this build (``<output_dir>/assets``), shared by the passes."""
    registry = ctx.values.get("asset_registry")
    if not isinstance(registry, AssetRegistry):
        registry = AssetRegistry(
            (Path(ctx.output_dir) / ASSETS_DIR).resolve(), copy_assets=ctx.copy_assets
        )
        ctx.values["asset_registry"] = registry
        ctx.values["assets"] = registry.assets_map
    return registry


def mermaid_caption(diagram: str) -> tuple[str | None, str]:
    """Split a leading ``%% caption`` comment off a Mermaid diagram (``media.py:85``)."""
    lines = diagram.splitlines()
    if lines and lines[0].strip().startswith("%%"):
        caption = lines[0].strip()[2:].strip() or None
        return caption, "\n".join(lines[1:])
    return None, diagram


def strip_theme_variant(src: str) -> str:
    """``a.png#only-dark`` → ``a.png`` (MkDocs Material light/dark variants)."""
    for marker in _THEME_VARIANTS:
        if src.endswith(marker):
            return src[: -len(marker)]
    return src


def _attr(attrs: model.Attrs, name: str) -> str | None:
    for key, value in attrs.kv:
        if key == name:
            return value
    return None


def _without_attrs(attrs: model.Attrs, *names: str) -> model.Attrs:
    kv = tuple(item for item in attrs.kv if item[0] not in names)
    return attrs if kv == attrs.kv else replace(attrs, kv=kv)


class _AssetPass:
    def __init__(self, document: Document, ctx: PassContext) -> None:
        self.document = document
        self.ctx = ctx
        self.backend = ctx.backend
        self.copy_assets = ctx.copy_assets
        self.registry = asset_registry(ctx)
        self.source_dir = Path(document.source_path).parent
        request = ctx.request
        backend = getattr(request, "diagrams_backend", None) or "playwright"
        user_agent = getattr(request, "http_user_agent", None)
        self.options = AssetOptions(
            assets=self.registry,
            source_dir=self.source_dir,
            document_path=Path(document.source_path),
            copy_assets=ctx.copy_assets,
            convert_assets=ctx.convert_assets,
            hash_assets=ctx.hash_assets,
            emitter=ctx.emitter,
            diagrams_backend=backend,
            http_user_agent=user_agent.strip()
            if isinstance(user_agent, str) and user_agent.strip()
            else None,
            mermaid_config=self._setting("mermaid_config") or None,
            drawio_crop=self._setting("drawio_crop"),
        )
        #: ``Image.id`` → caption text pulled from a ``%%`` line.
        self.captions: dict[int, str] = {}

    def _setting(self, name: str) -> Any:
        """A template override or front-matter setting, root or under ``press``."""
        value = lookup((name,), self.ctx.contexts)
        if value is MISSING:
            value = lookup(("press", name), self.ctx.contexts)
        return None if value is MISSING else value

    # -- helpers ------------------------------------------------------------

    def relative(self, stored: Path) -> str:
        return self.registry.latex_path(stored)

    def diagnostic(self, code: str, node: model.Node, message: str) -> None:
        self.ctx.diagnostics.emit(code, node.span, message)

    def literal(self, node: model.Node, text: str) -> model.Str:
        return model.Str(text=text, id=self.ctx.ids.next(), span=node.span)

    @staticmethod
    def alt_text(node: model.Image) -> str:
        from tmark.ir.walk import plain_text

        return plain_text(node.alt).strip()

    def placeholder(self, node: model.Image) -> model.Str:
        """What ``copy_assets=False`` rendered: the alt text, else ``[image]``."""
        return self.literal(node, self.alt_text(node) or "[image]")

    # -- dispatch ---------------------------------------------------------

    def image(self, node: model.Image) -> model.Node:
        generate = _attr(node.attrs, "generate")
        if generate is not None:
            if generate.strip().lower() == "mermaid":
                return self.mermaid(node, _attr(node.attrs, "code") or "")
            # Another generator (``python image``): the ``snippet``/``exec``
            # pass's job; an unrendered image is dropped by the writer.
            return node
        src = strip_theme_variant(node.src.strip())
        if not src:
            return node
        parsed = urlparse(src)
        if parsed.scheme == "data":
            return node
        if parsed.scheme in _REMOTE_SCHEMES and parsed.netloc:
            diagram = self._live_diagram(node, src)
            if diagram is not None:
                return self.mermaid(node, diagram)
            return self.remote(node, src)
        if src.lower().endswith(MERMAID_FILE_SUFFIXES):
            # A diagram file renders from its text like a fence (``%%``
            # caption included), as ``LaTeXWriter._load_mermaid_source`` did.
            resolved = self.resolve(src)
            if resolved is None:
                self.diagnostic("asset-missing", node, f"Mermaid diagram '{src}' not found")
                return self.literal(node, f"[asset: {src}: not found]")
            try:
                text = resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                self.diagnostic("asset-convert-failed", node, f"'{src}': {exc}")
                return self.literal(node, f"[asset: {src}: unreadable]")
            return self.mermaid(node, text)
        return self.local(node, src)

    def resolve(self, src: str) -> Path | None:
        """The local file ``src`` names, relative to the document's directory."""
        candidate = Path(src)
        resolved = candidate if candidate.is_absolute() else self.source_dir / candidate
        return resolved.resolve() if resolved.is_file() else None

    def _live_diagram(self, node: model.Image, src: str) -> str | None:
        try:
            return extract_mermaid_live_diagram(src)
        except Exception as exc:
            self.diagnostic("asset-convert-failed", node, f"'{src}': {exception_hint(exc) or exc}")
            return None

    # -- generated diagrams ---------------------------------------------

    def mermaid(self, node: model.Image, diagram: str) -> model.Node:
        from texsmith.adapters.transformers import mermaid2pdf

        caption, body = mermaid_caption(diagram)
        label = caption or "Mermaid diagram"
        if not self.copy_assets:
            return self.literal(node, label)
        if not looks_like_mermaid(body) or "```" in body or "~~~" in body:
            self.diagnostic("asset-convert-failed", node, "the fence is not a Mermaid diagram")
            return self.literal(node, f"[{label} unavailable]")
        options: dict[str, Any] = {
            "backend": self.options.diagrams_backend,
            "emitter": self.ctx.emitter,
        }
        if self.options.mermaid_config is not None:
            options["mermaid_config"] = self.options.mermaid_config
        try:
            artefact = mermaid2pdf(body, output_dir=self.registry.output_root, **options)
        except Exception as exc:
            hint = exception_hint(exc) or str(exc)
            self.diagnostic(
                "asset-convert-failed",
                node,
                f"Mermaid diagram could not be rendered ({hint}); install Docker and "
                "'minlag/mermaid-cli', or a Playwright browser, to enable diagram rendering",
            )
            return self.literal(node, f"[{label} unavailable]")
        key = f"mermaid::{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
        stored = self.registry.register(key, artefact)
        image = replace(
            node, src=self.relative(stored), attrs=_without_attrs(node.attrs, "code", "generate")
        )
        if caption:
            self.captions[image.id] = caption
        return image

    # -- remote -------------------------------------------------------------

    def remote(self, node: model.Image, url: str) -> model.Node:
        from texsmith.writers.latex.assets import store_remote_image_asset

        if not self.copy_assets:
            return self.placeholder(node)
        try:
            stored = store_remote_image_asset(self.options, url)
        except Exception as exc:
            self.diagnostic("asset-convert-failed", node, f"'{url}': {exception_hint(exc) or exc}")
            return self.literal(node, f"[asset: {url}: fetch failed]")
        return replace(node, src=self.relative(stored))

    # -- local --------------------------------------------------------------

    def local(self, node: model.Image, src: str) -> model.Node:
        if not self.copy_assets:
            return self.placeholder(node)
        resolved = self.resolve(src)
        if resolved is None:
            self.diagnostic("asset-missing", node, f"image '{src}' not found")
            return self.literal(node, f"[asset: {src}: not found]")
        options = dict(node.attrs.kv)
        try:
            if self.backend == "typst":
                stored = self._store_typst(resolved, options)
            else:
                from texsmith.writers.latex.assets import store_local_image_asset

                stored = store_local_image_asset(self.options, resolved, options=options)
        except Exception as exc:
            self.diagnostic("asset-convert-failed", node, f"'{src}': {exception_hint(exc) or exc}")
            return self.literal(node, f"[asset: {src}: conversion failed]")
        return replace(node, src=self.relative(stored))

    def _store_typst(self, resolved: Path, options: Mapping[str, str]) -> Path:
        """Typst reads PNG/JPEG/SVG/PDF natively: only diagrams are converted (to PDF)."""
        from texsmith.adapters.transformers import drawio2pdf, mermaid2pdf
        from texsmith.adapters.transformers.strategies import option_flag
        from texsmith.writers.latex.assets import (
            _asset_key,
            _conversion_cache_root,
            _persist_asset,
        )

        key = _asset_key(resolved, options)
        existing = self.registry.lookup(key)
        if existing is not None:
            return existing
        suffix = resolved.suffix.lower()
        backend = self.options.diagrams_backend
        if suffix in _DRAWIO_SUFFIXES:
            default = option_flag(self.options.drawio_crop, default=True)
            staged = drawio2pdf(
                resolved,
                output_dir=_conversion_cache_root(self.options),
                backend=backend,
                crop=option_flag(options.get("crop"), default=default),
                emitter=self.ctx.emitter,
            )
            final = ".pdf"
        elif suffix in MERMAID_FILE_SUFFIXES:
            staged = mermaid2pdf(
                resolved,
                output_dir=_conversion_cache_root(self.options),
                backend=backend,
                mermaid_config=self.options.mermaid_config,
                emitter=self.ctx.emitter,
            )
            final = ".pdf"
        else:
            staged = resolved
            final = suffix or ".bin"
        return _persist_asset(
            self.options,
            asset_key=key,
            staged_path=Path(staged),
            suffix=final,
            source_path=resolved,
        )

    # -- captions -----------------------------------------------------------

    def insert_captions(self, value: Any) -> Any:
        """Add a ``Caption`` after each paragraph holding a captioned diagram."""
        if isinstance(value, tuple):
            if value and all(isinstance(item, model.Block) for item in value):
                return self._caption_blocks(value)
            items = tuple(self.insert_captions(item) for item in value)
            return value if all(a is b for a, b in zip(items, value, strict=True)) else items
        if isinstance(value, model.Node | model.Record):
            changes = {
                name: mapped
                for name, child in iter_child_fields(value)
                if (mapped := self.insert_captions(child)) is not child
            }
            return replace(value, **changes) if changes else value
        return value

    def _caption_blocks(self, blocks: tuple[model.Block, ...]) -> tuple[model.Block, ...]:
        out: list[model.Block] = []
        changed = False
        for index, block in enumerate(blocks):
            rebuilt = self.insert_captions(block)
            if rebuilt is not block:
                changed = True
            out.append(rebuilt)
            image = self._captioned_image(rebuilt)
            if image is None:
                continue
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            preceding = blocks[index - 1] if index else None
            if isinstance(following, model.Caption) or (
                isinstance(preceding, model.Caption)
                and preceding.position is model.CaptionPosition.BEFORE
            ):
                continue
            text = self.captions[image.id]
            out.append(
                model.Caption(
                    kind=model.CaptionKind.FIGURE,
                    content=(model.Str(text=text, id=self.ctx.ids.next(), span=image.span),),
                    id=self.ctx.ids.next(),
                    span=image.span,
                )
            )
            changed = True
        return tuple(out) if changed else blocks

    def _captioned_image(self, block: model.Block) -> model.Image | None:
        if not isinstance(block, model.Para | model.Plain) or len(block.content) != 1:
            return None
        inline = block.content[0]
        if isinstance(inline, model.Link) and len(inline.content) == 1:
            inline = inline.content[0]
        if isinstance(inline, model.Image) and inline.id in self.captions:
            return inline
        return None


@spec("assets", after=("include", "snippet"), stage="pre", needs_io=True)
def run(document: Document, ctx: PassContext) -> Document:
    if document.ir is None:
        return document
    state = _AssetPass(document, ctx)

    def visit(node: model.Node) -> model.Node:
        if isinstance(node, model.Image):
            return state.image(node)
        return node

    rebuilt = map_tree(document.ir, visit)
    if state.captions:
        rebuilt = state.insert_captions(rebuilt)
    if rebuilt is document.ir:
        return document
    return document.evolve(ir=rebuilt)
