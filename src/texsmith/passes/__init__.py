"""The IR pass framework (``specs/migration/python-ir-and-passes.md`` §3).

A pass is a pure function ``(Document, PassContext) -> Document`` over the
generated models: it never mutates its input, returns the same object when it
has nothing to do, and otherwise ``document.evolve(...)`` with a rebuilt tree.
Failures never raise — a node is replaced by a visible literal and a
diagnostic is emitted at its span; an exception escaping a pass is a bug.

Two stages surround the one Rust step of the pipeline: ``pre`` passes run
before ``tmark.resolve`` (they may add, remove or rewrite blocks), ``post``
passes after it (they only slice the block list or compute per-body options,
so the ``Resolved`` of the whole document stays valid — decision X1).
:data:`DEFAULT_PIPELINE` is the explicit order; a template or plugin
registers a :class:`PassSpec` with ``after=`` and :func:`build_pipeline`
performs a stable topological sort, raising :class:`PassOrderError` on a
cycle. A template declares its own passes in its manifest
(``[latex.template] passes = ["pkg.module:run"]``, and the same under
``[typst.template]``); they are resolved when the manifest loads and handed
to :func:`build_pipeline` as ``extra`` while that template renders — never
globally.

Ids and spans. Three passes cite "span rule 1" and "span rule 2" in their
docstrings; here is what they are citing, written down at last.

**Rule 1 — a node rewritten in place keeps its id and its span.** The
construct is the one the author wrote; only its content changed. ``highlight``
turning a ``CodeBlock`` into a ``Div`` is the case: a diagnostic about that
code still points at the fence.

**Rule 2 — a node synthesised from another takes the source's span and a fresh
id.** The text is TeXSmith's, the *location* is the author's: a moustache
resolved by ``var``, a cluster split out by ``emoji``. Reusing the source's id
would put two nodes at one address; inventing a span would put a diagnostic
somewhere the author never wrote.

**Rule 3 — ``id`` and ``span`` take no part in equality or hashing**, so a
rebuilt subtree compares equal to its source when only identity changed
(``field(compare=False)`` on the generated models).

Ids are unique per file but not dense; the invariant that makes rule 2 safe is
"every id of every file is below :attr:`IdAllocator.floor`", maintained by
:meth:`IdAllocator.observe` after each parse.

``tests/passes/test_pass_framework.py`` checks rules 2 and 3 over the corpus:
no two nodes share an id, and no span names a file the build never registered.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from tmark.ir import model

from texsmith.diagnostics import DiagnosticEmitter, DiagnosticSink, FileTable, NullEmitter, Span
from texsmith.readers.loader import MemoryLoader


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.conversion.models import ConversionRequest
    from texsmith.core.documents import Document

__all__ = [
    "DEFAULT_PIPELINE",
    "REGISTRY",
    "IdAllocator",
    "Pass",
    "PassContext",
    "PassOrderError",
    "PassSpec",
    "SlotTemplate",
    "Stage",
    "build_pipeline",
    "highest_id",
    "register",
    "run_pipeline",
    "spec",
]

Pass = Callable[["Document", "PassContext"], "Document"]
Stage = Literal["pre", "post"]


class PassOrderError(ValueError):
    """A pipeline cannot be ordered: a cycle in ``after`` or an unknown pass name."""


@dataclass(slots=True)
class PassSpec:
    """One registered pass."""

    name: str
    run: Pass
    #: Names of the passes that must run before this one.
    after: tuple[str, ...] = ()
    #: Touches the file system, the network or a process; pure passes are
    #: tested without one.
    needs_io: bool = False
    #: ``"pre"`` runs before ``tmark.resolve``, ``"post"`` after it.
    stage: Stage = "pre"


class IdAllocator:
    """Fresh node ids above every id of every file of the build."""

    __slots__ = ("floor",)

    def __init__(self, floor: int = 1) -> None:
        self.floor = max(1, floor)

    def observe(self, root: Any) -> None:
        """Raise the floor above the ids of ``root`` (a document, node or record)."""
        self.floor = max(self.floor, highest_id(root) + 1)

    def next(self) -> int:
        """One fresh id."""
        value = self.floor
        self.floor += 1
        return value

    def reserve(self, count: int) -> int:
        """Reserve ``count`` consecutive ids; returns the first one."""
        first = self.floor
        self.floor += max(0, count)
        return first


def highest_id(root: Any) -> int:
    """The largest node id under ``root`` (a document, node, record or tuple), ``0`` when none."""
    return max(_iter_ids(root), default=0)


def _iter_ids(value: Any) -> Iterable[int]:
    if isinstance(value, (model.Node, model.Record)):
        for f in fields(value):
            item = getattr(value, f.name)
            if f.name == "id" and isinstance(item, int) and not isinstance(item, bool):
                yield item
            else:
                yield from _iter_ids(item)
    elif isinstance(value, tuple):
        for item in value:
            yield from _iter_ids(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_ids(item)


@dataclass(slots=True)
class SlotTemplate:
    """What the ``slots`` and ``headings`` passes know of the template binding."""

    default_slot: str = "mainmatter"
    #: The slot requests that survived template validation (``name -> selector``).
    requests: Mapping[str, str] = field(default_factory=dict)
    #: ``slot -> base level`` (``TemplateBinding.slot_levels()``).
    levels: Mapping[str, int] = field(default_factory=dict)
    #: Slots whose manifest declares ``strip_heading``.
    strip_heading: frozenset[str] = frozenset()
    #: The template base level for slots absent from ``levels``.
    base_level: int = 0


@dataclass(slots=True)
class PassContext:
    """Everything a pass may read besides the document; ``request`` is read-only."""

    files: FileTable = field(default_factory=FileTable)
    ids: IdAllocator = field(default_factory=IdAllocator)
    diagnostics: DiagnosticSink = field(default_factory=DiagnosticSink)
    loader: Any = field(default_factory=MemoryLoader)
    output_dir: Path = field(default_factory=Path.cwd)
    #: Absolute directories the ``include`` pass falls back to when a path does
    #: not resolve against the including file, in order (``--include-path``,
    #: ``press.include_paths``, the site's ``pymdownx.snippets`` base path).
    include_paths: tuple[Path, ...] = ()
    #: The directory a root-relative asset path (``/assets/logo.png``) resolves
    #: against — the site's ``docs_dir``. ``None``: a leading ``/`` names a
    #: filesystem path, as it does for a standalone conversion.
    root_dir: Path | None = None
    request: ConversionRequest | None = None
    #: Mustache contexts, first match wins (template overrides, front matter,
    #: defaults). The first mapping holds the template attribute overrides: the
    #: document's front matter merged with the CLI's ``-a key=value`` pairs, so
    #: ``-a solution=true`` reads back as ``ctx.attribute("solution")`` being
    #: ``True`` (``true``/``false`` become booleans, numbers become ``int`` or
    #: ``float``, and ``-a press.foo=1`` nests under ``press``). The attribute
    #: *defaults* a manifest declares are resolved by the template renderer and
    #: are not part of the contexts: a pass supplies its own default.
    contexts: tuple[Mapping[str, Any], ...] = ()
    #: Events only; findings go through ``diagnostics``.
    emitter: DiagnosticEmitter = field(default_factory=NullEmitter)
    template: SlotTemplate = field(default_factory=SlotTemplate)
    #: ``latex`` | ``typst`` | ``html`` — the backend the bodies are written for.
    backend: str = "latex"
    #: The merged ``code`` section of the template context (``engine``,
    #: ``style``, ``inline``), what ``build_writer_options`` reads too.
    code: Mapping[str, Any] = field(default_factory=dict)
    #: ``.bib`` files a pass wrote (``doi``): appended to
    #: ``ResolveOptions.bibliography`` and loaded into the conversion's collection.
    bibliography: list[Path] = field(default_factory=list)
    #: Pygments style definitions per style key (the ``highlight`` pass), the
    #: ``pygments_style_defs`` of ``ts-code``.
    pygments_styles: dict[str, str] = field(default_factory=dict)
    #: An object with ``fetch(doi) -> bibtex`` (``DoiBibliographyFetcher``);
    #: ``None`` builds the default one on first use.
    doi_fetcher: Any = None
    #: The generation flags of the request (``GenerationStrategy``): whether
    #: images are copied next to the output, converted to PDF, named by hash.
    copy_assets: bool = True
    convert_assets: bool = False
    hash_assets: bool = False
    #: What the passes hand back besides the document, keyed by name: the
    #: copied assets (``assets``), the font summaries of the ``scripts`` pass
    #: (``script_usage``, ``fallback_summary``), the ``emoji_mode`` the
    #: ``emoji`` pass resolved. Also where a test injects a helper (a fake
    #: ``script_detector``).
    values: dict[str, Any] = field(default_factory=dict)

    def attribute(self, name: str, default: Any = None) -> Any:
        """The template attribute ``name`` as the conversion resolved it, else ``default``.

        The lookup walks :attr:`contexts` in order — template overrides (front
        matter merged with the CLI's ``-a key=value``), then the front matter,
        then the mustache defaults — and a dotted ``name`` reaches into a nested
        mapping (``ctx.attribute("press.title")``). A template pass reads its
        options here: ``ctx.attribute("solution", False)`` is ``True`` under
        ``-a solution=true`` and falls back to the pass's own default when
        nothing overrides it, since manifest defaults never reach the contexts.
        """
        from texsmith.passes.var import MISSING, lookup

        value = lookup(name.split("."), self.contexts)
        return default if value is MISSING else value


# Registry and pipeline

REGISTRY: dict[str, PassSpec] = {}


def register(pass_spec: PassSpec) -> PassSpec:
    """Register a pass by name (a template or plugin adds its own here)."""
    REGISTRY[pass_spec.name] = pass_spec
    return pass_spec


def spec(
    name: str,
    *,
    after: Iterable[str] = (),
    needs_io: bool = False,
    stage: Stage = "pre",
) -> Callable[[Pass], Pass]:
    """Decorator registering ``run`` under ``name``."""

    def decorate(run: Pass) -> Pass:
        register(PassSpec(name=name, run=run, after=tuple(after), needs_io=needs_io, stage=stage))
        return run

    return decorate


#: The passes in their default order; ``resolve`` (Rust) runs between the
#: ``pre`` and the ``post`` stage.
DEFAULT_PIPELINE: tuple[str, ...] = (
    "include",
    "var",
    "title",
    "epigraph",
    "snippet",
    "assets",
    "doi",
    "emoji",
    "scripts",
    "slots",
    "headings",
    "highlight",
)


def build_pipeline(
    names: Iterable[str] = DEFAULT_PIPELINE,
    *,
    extra: Iterable[PassSpec] = (),
) -> tuple[PassSpec, ...]:
    """The passes to run, ordered.

    ``names`` gives the base order (registered passes, looked up by name);
    ``extra`` adds specs placed by their ``after`` constraints. The sort is
    stable: without constraints the listed order stands, and every ``pre``
    pass precedes every ``post`` pass.
    """
    import texsmith.passes.builtins

    ordered: list[PassSpec] = []
    for name in names:
        try:
            ordered.append(REGISTRY[name])
        except KeyError:
            raise PassOrderError(f"unknown pass '{name}'") from None
    ordered.extend(extra)
    by_name = {item.name: item for item in ordered}
    if len(by_name) != len(ordered):
        seen: set[str] = set()
        for item in ordered:
            if item.name in seen:
                raise PassOrderError(f"pass '{item.name}' listed twice")
            seen.add(item.name)

    for item in ordered:
        for dependency in item.after:
            if dependency not in by_name:
                raise PassOrderError(f"pass '{item.name}' runs after unknown pass '{dependency}'")

    pre = [item for item in ordered if item.stage == "pre"]
    post = [item for item in ordered if item.stage == "post"]
    return (*_sort_stage(pre, by_name), *_sort_stage(post, by_name))


def _sort_stage(items: list[PassSpec], by_name: Mapping[str, PassSpec]) -> list[PassSpec]:
    """Stable topological order of ``items`` under their ``after`` constraints.

    A depth-first visit in list order: a pass is placed right after the last of
    its dependencies, and passes without constraints keep their listed order.
    """
    stage_names = {item.name for item in items}
    for item in items:
        for dep in item.after:
            if by_name[dep].stage == "post" and item.stage == "pre":
                raise PassOrderError(
                    f"pre-resolve pass '{item.name}' cannot run after post-resolve pass '{dep}'"
                )
    state: dict[str, str] = {}
    result: list[PassSpec] = []

    def visit(name: str, trail: tuple[str, ...]) -> None:
        status = state.get(name)
        if status == "done":
            return
        if status == "active":
            cycle = " -> ".join((*trail[trail.index(name) :], name))
            raise PassOrderError(f"cycle in pass ordering: {cycle}")
        state[name] = "active"
        for dep in by_name[name].after:
            if dep in stage_names:
                visit(dep, (*trail, name))
        state[name] = "done"
        result.append(by_name[name])

    for item in items:
        visit(item.name, ())
    return result


def run_pipeline(
    document: Document,
    ctx: PassContext,
    pipeline: Iterable[PassSpec] = (),
    *,
    resolve: Callable[[Document, PassContext], Document] | None = None,
) -> Document:
    """Run ``pipeline`` on ``document``: the ``pre`` passes, ``resolve``, the ``post`` passes."""
    passes = tuple(pipeline) if pipeline else build_pipeline()
    current = document
    for item in passes:
        if item.stage != "pre":
            continue
        current = item.run(current, ctx)
    if resolve is not None:
        current = resolve(current, ctx)
    for item in passes:
        if item.stage != "post":
            continue
        current = item.run(current, ctx)
    return current
