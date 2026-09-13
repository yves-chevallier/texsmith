"""The recording emitter the tests assert findings against."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from texsmith.diagnostics import Diagnostic, Severity, SinkEmitter


class RecordingEmitter(SinkEmitter):
    """A presenter that keeps what it is shown, for tests that assert on findings.

    Collecting belongs to the sink, so an emitter only implements ``render``
    and ``event``. The records are also in ``self.sink``, with their codes and
    spans; ``warnings`` and ``errors`` are the messages alone, which is what
    most assertions want.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rendered: list[tuple[Diagnostic, BaseException | None]] = []
        self.events: list[tuple[str, dict[str, Any]]] = []

    def render(self, diagnostic: Diagnostic, cause: BaseException | None) -> None:
        self.rendered.append((diagnostic, cause))

    def event(self, name: str, payload: Mapping[str, Any]) -> None:
        self.events.append((name, dict(payload)))

    @property
    def messages(self) -> list[str]:
        """Every rendered message, in emission order."""
        return [record.message for record, _ in self.rendered]

    @property
    def warnings(self) -> list[str]:
        """The messages of the records below ``error``."""
        return [record.message for record, _ in self.rendered if record.severity < Severity.ERROR]

    @property
    def errors(self) -> list[str]:
        return [record.message for record, _ in self.rendered if record.severity is Severity.ERROR]

    def codes(self) -> list[str]:
        return [record.code for record, _ in self.rendered]
