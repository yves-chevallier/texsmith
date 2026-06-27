"""Tests for template-scoped render extensions (custom @reads / @writes)."""

from __future__ import annotations

import types

import pytest

from texsmith.adapters.latex.renderer import LaTeXRenderer
from texsmith.core.conversion.core import _apply_template_render_extensions
from texsmith.core.templates.extensions import (
    apply_render_extensions,
    resolve_reader_modules,
    resolve_writer_class,
)
from texsmith.core.templates.manifest import TemplateError, TemplateInfo
from texsmith.ir import nodes as ir
from texsmith.readers.html import build_reader_registry
from texsmith.readers.html.registry import ReadLevel, reads
from texsmith.writers.latex.writer import LaTeXWriter
from texsmith.writers.registry import writes


def _custom_reader_module() -> types.ModuleType:
    """A throwaway module exposing one @reads lowering for <blink>."""
    module = types.ModuleType("exam_test_reader")

    @reads("blink", level=ReadLevel.INLINE, priority=200, name="t_blink")
    def read_blink(tag, ctx):
        return ir.RawInline("latex", r"\BLINK")

    module.read_blink = read_blink
    return module


class _UpperWriter(LaTeXWriter):
    """A LaTeXWriter subclass that upper-cases plain text."""

    @writes(ir.Str)
    def _str(self, node: ir.Str) -> str:
        return node.text.upper()


# -- manifest parsing ------------------------------------------------------


def test_template_info_parses_readers_and_writer() -> None:
    info = TemplateInfo(
        name="exam",
        version="1.0",
        readers=["pkg.reader_a", "pkg.reader_b"],
        writer="pkg.writer:ExamWriter",
    )
    assert info.readers == ["pkg.reader_a", "pkg.reader_b"]
    assert info.writer == "pkg.writer:ExamWriter"


def test_template_info_defaults_have_no_extensions() -> None:
    info = TemplateInfo(name="plain", version="1.0")
    assert info.readers == []
    assert info.writer is None


# -- resolution ------------------------------------------------------------


def test_resolve_reader_modules_imports_real_modules() -> None:
    modules = resolve_reader_modules(["texsmith.readers.html.blocks"])
    assert len(modules) == 1
    assert modules[0].__name__ == "texsmith.readers.html.blocks"


def test_resolve_reader_modules_bad_path_raises() -> None:
    with pytest.raises(TemplateError, match="could not be imported"):
        resolve_reader_modules(["texsmith.does_not_exist_xyz"])


def test_resolve_writer_class_accepts_subclass() -> None:
    cls = resolve_writer_class("texsmith.writers.latex.writer:LaTeXWriter")
    assert cls is LaTeXWriter


def test_resolve_writer_class_rejects_non_writer() -> None:
    with pytest.raises(TemplateError, match="must resolve to a LaTeXWriter subclass"):
        resolve_writer_class("builtins:dict")


# -- the renderer seams actually change output -----------------------------


def test_custom_reader_changes_output() -> None:
    renderer = LaTeXRenderer()
    renderer.reader_registry = build_reader_registry([_custom_reader_module()])
    out = renderer.render("<p>before <blink>x</blink> after</p>")
    assert r"\BLINK" in out


def test_custom_writer_changes_output() -> None:
    renderer = LaTeXRenderer()
    renderer.writer_class = _UpperWriter
    out = renderer.render("<p>hello world</p>")
    assert "HELLO WORLD" in out


# -- apply_render_extensions glue -----------------------------------------


def test_apply_render_extensions_sets_both_seams() -> None:
    renderer = LaTeXRenderer()
    apply_render_extensions(
        renderer,
        readers=["texsmith.readers.html.blocks"],
        writer="texsmith.writers.latex.writer:LaTeXWriter",
    )
    assert renderer.reader_registry is not None
    assert renderer.writer_class is LaTeXWriter


def test_apply_render_extensions_noop_when_empty() -> None:
    renderer = LaTeXRenderer()
    apply_render_extensions(renderer, readers=None, writer=None)
    assert renderer.reader_registry is None
    assert renderer.writer_class is LaTeXWriter


# -- core.py binding glue --------------------------------------------------


def test_apply_template_render_extensions_reads_binding_extras() -> None:
    renderer = LaTeXRenderer()

    runtime = types.SimpleNamespace(
        extras={"writer": "texsmith.writers.latex.writer:LaTeXWriter", "readers": []}
    )
    binding = types.SimpleNamespace(runtime=runtime)

    _apply_template_render_extensions(renderer, binding)  # type: ignore[arg-type]
    assert renderer.writer_class is LaTeXWriter


def test_apply_template_render_extensions_noop_without_runtime() -> None:
    renderer = LaTeXRenderer()
    binding = types.SimpleNamespace(runtime=None)
    _apply_template_render_extensions(renderer, binding)  # type: ignore[arg-type]
    assert renderer.reader_registry is None
