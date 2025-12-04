"""Small logging helpers that integrate with the TeXSmith CLI."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import typer


def _resolve_state() -> object | None:
    try:
        from texsmith.ui.cli.state import get_cli_state
    except Exception:  # pragma: no cover - fallback when CLI is unavailable
        return None
    try:
        return get_cli_state(create=False)
    except Exception:
        return None


@dataclass(slots=True)
class FontPipelineLogger:
    """Light wrapper around the CLI state with graceful degradation."""

    verbose: bool = False
    _state: object | None = None

    def __post_init__(self) -> None:
        self._state = _resolve_state()

    def _render_message(self, message: str, args: tuple[Any, ...]) -> str:
        if args:
            try:
                message = message % args
            except Exception:
                message = " ".join([message, *(str(arg) for arg in args)])
        return message

    def info(self, message: str, *args: Any) -> None:
        message = self._render_message(message, args)
        if self._state is not None:
            try:
                console = self._state.console
                console.log(message)
            except Exception:  # pragma: no cover - defensive fallback
                pass
            else:
                return
        typer.echo(message)

    def warning(self, message: str, *args: Any) -> None:
        message = self._render_message(message, args)
        if self._state is not None:
            try:
                from texsmith.ui.cli.state import emit_warning

                emit_warning(message)
            except Exception:  # pragma: no cover - defensive fallback
                pass
            else:
                return
        typer.secho(message, fg="yellow")

    def notice(self, message: str, *args: Any) -> None:
        """Alias for info to mirror the CLI vocabulary."""
        self.info(message, *args)

    def debug(self, message: str, *args: Any) -> None:
        """Emit a debug/verbose message when verbose mode is enabled."""
        if not self.verbose:
            return
        self.info(message, *args)

    @contextmanager
    def progress(self, task: str, total: int | None = None) -> Iterator[callable]:
        """Yield a progress updater. Falls back to a no-op when Rich is absent."""
        try:
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TaskID,
                TextColumn,
                TimeElapsedColumn,
            )
        except Exception:  # pragma: no cover - Rich not available
            count = 0

            def _advance(step: int = 1) -> None:
                nonlocal count
                count += step
                if total:
                    typer.echo(f"{task}: {count}/{total}", err=True)
                elif self.verbose:
                    typer.echo(f"{task}: {count}", err=True)

            yield _advance
            return

        if self._state is not None:
            console = self._state.console
        else:
            from rich.console import Console

            console = Console()

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[bold cyan]{task}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}" if total else "{task.completed}"),
            TimeElapsedColumn(),
            console=console,
            transient=not self.verbose,
        ) as progress:
            task_id: TaskID = progress.add_task(task, total=total)

            def _advance(step: int = 1) -> None:
                progress.update(task_id, advance=step)

            yield _advance


__all__ = ["FontPipelineLogger"]
