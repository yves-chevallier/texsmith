from __future__ import annotations

import logging

import pytest

from texsmith.core.conversion.debug import format_user_friendly_render_error
from texsmith.core.diagnostics import LoggingEmitter, NullEmitter
from texsmith.core.exceptions import LatexRenderingError, TransformerExecutionError
from texsmith.ui.cli.diagnostics import CliEmitter
from texsmith.ui.cli.state import ensure_rich_compat, set_cli_state


def _raise_transformer_execution_error() -> None:
    raise TransformerExecutionError("Docker executable could not be located.")


def _raise_nested_render_error() -> None:
    try:
        _raise_transformer_execution_error()
    except TransformerExecutionError as exc:
        raise LatexRenderingError("render failed") from exc


def test_null_emitter_is_noop(caplog: pytest.LogCaptureFixture) -> None:
    emitter = NullEmitter()
    with caplog.at_level(logging.WARNING):
        emitter.warning("nothing to see")
        emitter.error("still quiet")
    assert not caplog.records
    emitter.event("ignored", {"value": 1})
    assert emitter.debug_enabled is False


def test_logging_emitter_logs_messages(caplog: pytest.LogCaptureFixture) -> None:
    emitter = LoggingEmitter(debug_enabled=True)
    with caplog.at_level(logging.ERROR):
        emitter.error("boom")
    assert any(record.message == "boom" for record in caplog.records)
    assert emitter.debug_enabled is True


def test_cli_emitter_bridges_state(capsys: pytest.CaptureFixture[str]) -> None:
    ensure_rich_compat()
    state = set_cli_state(verbosity=1, debug=False)
    emitter = CliEmitter(state=state)

    emitter.warning("Heads up", exc=None)
    emitter.error("Boom", exc=None)
    emitter.event("custom", {"flag": True})

    captured = capsys.readouterr()
    combined_output = f"{captured.out}\n{captured.err}"
    assert "Heads up" in combined_output
    assert "Boom" in combined_output
    assert state.consume_events("custom") == [{"flag": True}]


def test_format_user_friendly_render_error_reports_root_cause() -> None:
    try:
        _raise_nested_render_error()
    except LatexRenderingError as error:
        message = format_user_friendly_render_error(error)
    assert "Docker executable could not be located." in message
    assert "--debug" in message
