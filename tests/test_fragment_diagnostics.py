"""``render_fragments``: a misbehaving ``should_render`` emits ``fragment-manifest``.

Both fragment shapes go through the same ``render_fragments`` loop —
``FragmentDefinition`` (TOML/entrypoint fragments) and ``BaseFragment``
(Python class fragments) — and each has its own ``try/except`` around
``should_render``. Both used to fall through to a bare ``warnings.warn``,
invisible to ``--strict``/``--diagnostics-json``; see
``specs/refactoring/status.md`` step 09.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

import pytest

from texsmith.core.fragments import (
    FRAGMENT_ROOT,
    FragmentDefinition,
    FragmentPiece,
    FragmentRegistry,
    register_fragment,
    render_fragments,
)
from texsmith.core.fragments.base import BaseFragment
from texsmith.diagnostics import LoggingEmitter


def _write_piece(tmp_path: Path, name: str = "frag.tex.jinja") -> FragmentPiece:
    template = tmp_path / name
    template.write_text("ok\n", encoding="utf-8")
    return FragmentPiece(template_path=template, kind="inline", variable="extra_packages")


def test_should_render_raising_in_a_fragment_definition_emits_fragment_manifest(
    tmp_path: Path,
) -> None:
    def _boom(context: Any) -> bool:
        _ = context
        raise RuntimeError("boom")

    definition = FragmentDefinition(
        name="broken-def",
        pieces=[_write_piece(tmp_path)],
        should_render=_boom,
    )
    register_fragment(definition)
    emitter = LoggingEmitter()

    render_fragments(["broken-def"], context={}, output_dir=tmp_path, emitter=emitter)

    codes = [d.code for d in emitter.sink]
    assert codes == ["fragment-manifest"]
    assert "broken-def" in emitter.sink.sorted()[0].message
    assert "should_render() raised" in emitter.sink.sorted()[0].message


class _BrokenShouldRender(BaseFragment[dict]):
    name: ClassVar[str] = "broken-class"
    description: ClassVar[str] = "Fragment whose predicate always raises."
    pieces: ClassVar[list[FragmentPiece]] = []
    attributes: ClassVar[dict] = {}
    config_cls: ClassVar[type] = dict

    def build_config(self, context, overrides=None, *, emitter=None):
        _ = overrides, emitter
        return {}

    def inject(self, config, context, overrides=None, *, emitter=None) -> None:
        _ = config, context, overrides, emitter

    def should_render(self, config: dict) -> bool:
        _ = config
        raise RuntimeError("boom")


def test_should_render_raising_in_a_base_fragment_emits_fragment_manifest(tmp_path: Path) -> None:
    fragment = _BrokenShouldRender()
    fragment.pieces = [_write_piece(tmp_path)]
    register_fragment(fragment)
    emitter = LoggingEmitter()

    render_fragments(["broken-class"], context={}, output_dir=tmp_path, emitter=emitter)

    codes = [d.code for d in emitter.sink]
    assert codes == ["fragment-manifest"]
    assert "broken-class" in emitter.sink.sorted()[0].message


class _BrokenEntryPoint:
    name = "broken-entry-point"

    def load(self) -> Any:
        raise RuntimeError("broken plugin")


def test_broken_entry_point_logs_instead_of_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """No document/emitter exists at registry-construction time (import time).

    ``FragmentRegistry.__init__`` runs once, for the module-level singleton,
    before any run's emitter exists — so this stays on the module logger
    rather than routing through the diagnostics sink (status.md step 09).
    """
    monkeypatch.setattr("importlib.metadata.entry_points", lambda **_: [_BrokenEntryPoint()])

    with caplog.at_level(logging.WARNING, logger="texsmith.core.fragments"):
        FragmentRegistry(root=FRAGMENT_ROOT, default_order=[])

    assert any("broken-entry-point" in record.message for record in caplog.records)


def test_should_render_raising_without_an_emitter_stays_quiet(tmp_path: Path) -> None:
    """No emitter reachable: the default is silence, not a crash."""
    definition = FragmentDefinition(
        name="broken-def-quiet",
        pieces=[_write_piece(tmp_path)],
        should_render=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),  # noqa: ARG005
    )
    register_fragment(definition)

    render_fragments(["broken-def-quiet"], context={}, output_dir=tmp_path)
