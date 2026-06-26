"""Rich-console rendering of structured LaTeX log messages.

Split out of :mod:`texsmith.adapters.latex.engines.latex.log` so the parsing of
LaTeX output (``LatexLogParser``) and its presentation (this renderer) stay
separate concerns. The shared message types and highlight patterns live in
``log``; this module only consumes them.
"""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from rich.console import Console
from rich.text import Text

from .log import (
    _HIGHLIGHT_PATTERN,
    _PATH_LINE_PATTERN,
    _STRING_LITERAL_PATTERN,
    _TEX_ASSIGN_PATTERN,
    LatexMessage,
    LatexMessageSeverity,
)


class LatexLogRenderer:
    """Render structured LaTeX messages to a Rich console."""

    _SUMMARY_STYLE: ClassVar[dict[LatexMessageSeverity, str]] = {
        LatexMessageSeverity.INFO: "cyan",
        LatexMessageSeverity.WARNING: "bold yellow",
        LatexMessageSeverity.ERROR: "bold red",
    }
    _DETAIL_STYLE: ClassVar[dict[LatexMessageSeverity, str]] = {
        LatexMessageSeverity.INFO: "cyan",
        LatexMessageSeverity.WARNING: "yellow",
        LatexMessageSeverity.ERROR: "red",
    }

    def __init__(self, console: Console) -> None:
        self.console = console
        self.messages: list[LatexMessage] = []
        self._current_messages: list[LatexMessage] = []
        self._pending: LatexMessage | None = None
        self._pending_heading: bool = False
        self._branch_stack: list[bool] = []
        self._heading_open = False
        self._heading_next_bold = False

    def consume(self, message: LatexMessage) -> None:
        """Display a single message, queueing it for tree-aware formatting."""
        heading_for_message = False
        heading_state = self._split_heading_line(message.summary)
        if heading_state is not None:
            kind, remainder = heading_state
            if kind == "rule":
                self._heading_open = not self._heading_open
                self._heading_next_bold = self._heading_open
                return
            if remainder:
                heading_for_message = True
                message = replace(message, summary=remainder)
                if not self._heading_open:
                    self._heading_open = True
            self._heading_next_bold = False

        if self._heading_next_bold:
            heading_for_message = True
            self._heading_next_bold = False

        if self._is_run_boundary(message):
            self._current_messages.clear()
        self.messages.append(message)
        self._current_messages.append(message)
        next_indent = message.indent
        self._emit_pending(next_indent)
        self._pending = message
        self._pending_heading = heading_for_message

    def summarize(self) -> None:
        """Print a summary of processed messages grouped by severity."""
        self._emit_pending(None)
        warnings = sum(
            1 for msg in self._current_messages if msg.severity is LatexMessageSeverity.WARNING
        )
        errors = sum(
            1 for msg in self._current_messages if msg.severity is LatexMessageSeverity.ERROR
        )
        info = sum(1 for msg in self._current_messages if msg.severity is LatexMessageSeverity.INFO)
        summary_parts = [
            f"errors: {errors}",
            f"warnings: {warnings}",
        ]
        if info:
            summary_parts.append(f"info: {info}")
        style = "green" if errors == 0 else "bold red"
        self.console.print(Text("Summary — " + ", ".join(summary_parts), style=style))

    def _emit_pending(self, next_indent: int | None) -> None:
        if self._pending is None:
            return
        message = self._pending
        heading = self._pending_heading
        depth = message.indent
        connector = self._select_connector(depth, next_indent)

        branches_snapshot = list(self._branch_stack)
        while len(branches_snapshot) <= depth:
            branches_snapshot.append(False)

        prefix = self._build_prefix(depth, connector, branches_snapshot)
        self._print_message(message, prefix, branches_snapshot, heading)
        self._update_branch_stack(depth, connector, next_indent)
        self._pending = None
        self._pending_heading = False

    def _print_message(
        self,
        message: LatexMessage,
        prefix: Text,
        branches_snapshot: list[bool],
        heading: bool = False,
    ) -> None:
        style = self._SUMMARY_STYLE.get(message.severity, "white")
        detail_style = self._DETAIL_STYLE.get(message.severity, "white")
        icon = {
            LatexMessageSeverity.ERROR: "x",
            LatexMessageSeverity.WARNING: "▲",
        }.get(message.severity, "")

        header = Text()
        header.append_text(prefix)

        summary_style = style
        if heading:
            summary_style = (
                f"{summary_style} bold" if "bold" not in summary_style else summary_style
            )
        if _HIGHLIGHT_PATTERN.match(message.summary):
            summary_style = f"{summary_style} bold" if summary_style else "bold"
        if message.severity is LatexMessageSeverity.INFO and _TEX_ASSIGN_PATTERN.search(
            message.summary
        ):
            summary_style = "grey58"
        if _PATH_LINE_PATTERN.match(message.summary):
            summary_style = "grey50"
        if icon:
            header.append(f"{icon} ", style=style)
        summary_text = Text(message.summary, style=summary_style)
        self._highlight_strings(summary_text)
        header.append_text(summary_text)
        self.console.print(header)

        if not message.details:
            return

        for index, detail in enumerate(message.details):
            is_last = index == len(message.details) - 1
            connector = "└" if is_last else "├"
            detail_branches = branches_snapshot.copy()
            while len(detail_branches) <= message.indent:
                detail_branches.append(False)
            detail_branches[message.indent] = not is_last

            detail_prefix = self._build_prefix(
                message.indent + 1,
                connector,
                detail_branches,
            )
            detail_style_local = detail_style
            if _TEX_ASSIGN_PATTERN.search(detail):
                detail_style_local = "grey58"
            if _PATH_LINE_PATTERN.match(detail):
                detail_style_local = "grey50"
            detail_text = Text(detail, style=detail_style_local)
            self._highlight_strings(detail_text)
            detail_line = Text()
            detail_line.append_text(detail_prefix)
        detail_line.append_text(detail_text)
        self.console.print(detail_line)

    @staticmethod
    def _is_run_boundary(message: LatexMessage) -> bool:
        if message.severity is not LatexMessageSeverity.INFO:
            return False
        summary = message.summary.strip()
        return summary.startswith("Run number ") and " of rule " in summary

    @staticmethod
    def _highlight_strings(text: Text) -> None:
        for match in _STRING_LITERAL_PATTERN.finditer(text.plain):
            start, end = match.span()
            text.stylize("magenta", start, end)

    def _select_connector(self, depth: int, next_indent: int | None) -> str:
        if next_indent is None or next_indent < depth:
            return "└"
        return "├"

    @staticmethod
    def _build_prefix(depth: int, connector: str, branches: list[bool]) -> Text:
        prefix = Text()
        for level in range(depth):
            active = branches[level] if level < len(branches) else False
            glyph = "│  " if active else "   "
            prefix.append(glyph, style="grey35")
        prefix.append(f"{connector}─ ", style="grey35")
        return prefix

    def _update_branch_stack(
        self,
        depth: int,
        connector: str,
        next_indent: int | None,
    ) -> None:
        while len(self._branch_stack) <= depth:
            self._branch_stack.append(False)
        self._branch_stack[depth] = connector == "├"

        if next_indent is not None:
            for idx in range(next_indent + 1, len(self._branch_stack)):
                if idx > depth:
                    self._branch_stack[idx] = False
        if connector == "└":
            self._branch_stack[depth] = False
        del self._branch_stack[depth + 1 :]

    @staticmethod
    def _split_heading_line(summary: str) -> tuple[str, str | None] | None:
        candidate = summary.strip()
        if not candidate or candidate[0] != "-":
            return None
        dash_count = 0
        for ch in candidate:
            if ch != "-":
                break
            dash_count += 1
        if dash_count < 5:
            return None
        remainder = candidate[dash_count:].strip()
        if not remainder:
            return ("rule", None)
        return ("combined", remainder)
