from __future__ import annotations

import logging
from pathlib import Path

import pytest

from texsmith.core.diagnostics import (
    DiagnosticEmitter,
    LoggingEmitter,
    NullEmitter,
    emit_diagnostic,
)
from texsmith.core.exceptions import (
    LatexRenderingError,
    TransformerExecutionError,
    format_user_friendly_render_error,
)
from texsmith.diagnostics import NO_SPAN, Diagnostic, Severity, Span
from texsmith.ui.cli.diagnostics import CliEmitter
from texsmith.ui.cli.state import ensure_rich_compat, set_cli_state


def _raise_transformer_execution_error() -> None:
    raise TransformerExecutionError("Docker executable could not be located.")


def _raise_nested_render_error() -> None:
    try:
        _raise_transformer_execution_error()
    except TransformerExecutionError as exc:
        raise LatexRenderingError("render failed") from exc


def test_null_emitter_shows_nothing_but_keeps_everything(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Silence is a rendering choice: the records stay available to the caller."""
    emitter = NullEmitter()
    with caplog.at_level(logging.WARNING):
        emit_diagnostic(emitter, "conversion-failed", "still quiet")
        emitter.diagnostic(Diagnostic("asset-missing", Severity.WARNING, NO_SPAN, "gone"))
    assert not caplog.records
    emitter.event("ignored", {"value": 1})
    assert emitter.debug_enabled is False
    assert isinstance(emitter, DiagnosticEmitter)
    assert [record.code for record in emitter.sink] == ["conversion-failed", "asset-missing"]


def test_logging_emitter_logs_the_rendered_line(caplog: pytest.LogCaptureFixture) -> None:
    emitter = LoggingEmitter(debug_enabled=True)
    with caplog.at_level(logging.ERROR):
        emit_diagnostic(emitter, "conversion-failed", "boom")
    assert [record.message for record in caplog.records] == ["error conversion-failed: boom"]
    assert emitter.debug_enabled is True
    (recorded,) = emitter.sink
    assert recorded.code == "conversion-failed"
    # The severity came from the code table, not from the call site.
    assert recorded.severity is Severity.ERROR
    assert recorded.span == NO_SPAN


def test_logging_emitter_keeps_the_cause_as_exc_info(caplog: pytest.LogCaptureFixture) -> None:
    emitter = LoggingEmitter()
    cause = ValueError("root")
    with caplog.at_level(logging.WARNING):
        emit_diagnostic(emitter, "asset-missing", "Heads up", exc=cause)
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert record.exc_info is not None
    assert record.exc_info[1] is cause


def test_emitter_deduplicates_identical_records(caplog: pytest.LogCaptureFixture) -> None:
    emitter = LoggingEmitter()
    with caplog.at_level(logging.WARNING):
        emit_diagnostic(emitter, "asset-missing", "twice")
        emit_diagnostic(emitter, "asset-missing", "twice")
    assert len(emitter.sink) == 1
    assert len(caplog.records) == 1


def test_a_filtering_subclass_sees_every_record() -> None:
    """``emit_diagnostic`` goes through ``diagnostic()``, not straight to the sink.

    The render command filters ``--deprecated`` by overriding ``diagnostic``;
    a helper that reached ``sink.add`` itself would slip past it.
    """

    class Dropping(LoggingEmitter):
        def diagnostic(self, diagnostic: Diagnostic, cause: BaseException | None = None) -> None:
            del cause
            if diagnostic.severity is not Severity.WARNING:
                super().diagnostic(diagnostic)

    emitter = Dropping()
    emit_diagnostic(emitter, "asset-missing", "dropped")
    emit_diagnostic(emitter, "conversion-failed", "kept")
    emitter.diagnostic(Diagnostic("asset-missing", Severity.WARNING, NO_SPAN, "also dropped"))

    assert [record.message for record in emitter.sink] == ["kept"]


def test_the_cause_survives_the_diagnostic_hop(caplog: pytest.LogCaptureFixture) -> None:
    """A subclass that forwards through ``diagnostic`` keeps the ``-v`` context."""

    class Passing(LoggingEmitter):
        def diagnostic(self, diagnostic: Diagnostic, cause: BaseException | None = None) -> None:
            super().diagnostic(diagnostic, cause)

    emitter = Passing()
    cause = ValueError("root")
    with caplog.at_level(logging.WARNING):
        emit_diagnostic(emitter, "asset-missing", "Heads up", exc=cause)
    (record,) = caplog.records
    assert record.exc_info is not None
    assert record.exc_info[1] is cause


def test_emitter_renders_a_located_record(caplog: pytest.LogCaptureFixture) -> None:
    emitter = LoggingEmitter()
    file_id = emitter.files.add(Path("doc.md"), "a\n\nhello @x\n")
    with caplog.at_level(logging.WARNING):
        emitter.diagnostic(
            Diagnostic(
                "ref-unresolved",
                Severity.WARNING,
                Span(file_id, 9, 11),
                "`@x` does not resolve",
                origin="tmark",
            )
        )
    assert caplog.records[0].message == "doc.md:3:7: warning ref-unresolved: `@x` does not resolve"


def test_cli_emitter_bridges_state(capsys: pytest.CaptureFixture[str]) -> None:
    ensure_rich_compat()
    state = set_cli_state(verbosity=1, debug=False)
    emitter = CliEmitter(state=state)

    emit_diagnostic(emitter, "asset-missing", "Heads up")
    emit_diagnostic(emitter, "conversion-failed", "Boom")
    emitter.event("custom", {"flag": True})

    captured = capsys.readouterr()
    assert "warning asset-missing: Heads up" in captured.err
    assert "error conversion-failed: Boom" in captured.err
    assert state.consume_events("custom") == [{"flag": True}]
    assert [d.severity for d in emitter.sink] == [Severity.WARNING, Severity.ERROR]
    assert emitter.sink.strict_failed()


def test_cli_emitter_shows_the_cause_at_verbosity_one(capsys: pytest.CaptureFixture[str]) -> None:
    ensure_rich_compat()
    state = set_cli_state(verbosity=1, debug=False)
    emitter = CliEmitter(state=state)

    emit_diagnostic(emitter, "asset-missing", "Fetch failed", exc=OSError("connection refused"))

    err = capsys.readouterr().err
    assert "warning asset-missing: Fetch failed" in err
    assert "connection refused" in err
    assert "type: OSError" in err


def test_cli_emitter_quiet_hides_hints_and_info(capsys: pytest.CaptureFixture[str]) -> None:
    ensure_rich_compat()
    state = set_cli_state(verbosity=0, debug=False, quiet=True)
    emitter = CliEmitter(state=state)

    emitter.diagnostic(Diagnostic("lead-promotion", Severity.INFO, NO_SPAN, "promoted"))
    emitter.diagnostic(Diagnostic("heading-skip", Severity.HINT, NO_SPAN, "skipped"))
    emitter.diagnostic(Diagnostic("asset-missing", Severity.WARNING, NO_SPAN, "gone"))

    err = capsys.readouterr().err
    assert "promoted" not in err
    assert "skipped" not in err
    assert "warning asset-missing: gone" in err
    # Hidden is not dropped: the JSON dump and the counts still see them.
    assert len(emitter.sink) == 3
    state.quiet = False


def test_format_user_friendly_render_error_reports_root_cause() -> None:
    try:
        _raise_nested_render_error()
    except LatexRenderingError as error:
        message = format_user_friendly_render_error(error)
    assert "Docker executable could not be located." in message
    assert "--debug" in message
