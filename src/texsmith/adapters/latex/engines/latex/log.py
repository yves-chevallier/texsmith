"""Utilities for parsing and presenting output from LaTeX engine builds."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
import re
import selectors
import subprocess
from typing import ClassVar, TextIO, cast

from rich.console import Console
from rich.text import Text


class LatexMessageSeverity(Enum):
    """Classification severity extracted from LaTeX output."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class LatexMessage:
    """Structured LaTeX message extracted from the build log."""

    severity: LatexMessageSeverity
    summary: str
    details: list[str] = field(default_factory=list)
    indent: int = 0


_MESSAGE_PATTERNS: list[tuple[re.Pattern[str], LatexMessageSeverity]] = [
    (re.compile(r"^! (?P<summary>.+)$"), LatexMessageSeverity.ERROR),
    (
        re.compile(r"^Latexmk: (?P<summary>.+\b(?:error|failed|failure).*)$", re.I),
        LatexMessageSeverity.ERROR,
    ),
    (
        re.compile(r"^Latexmk: (?P<summary>Errors, .*)$", re.I),
        LatexMessageSeverity.ERROR,
    ),
    (
        re.compile(r"^LaTeX Warning: (?P<summary>.+)$"),
        LatexMessageSeverity.WARNING,
    ),
    (
        re.compile(r"^Package (?P<context>\S+) Warning: (?P<summary>.+)$"),
        LatexMessageSeverity.WARNING,
    ),
    (
        re.compile(r"^Class (?P<context>\S+) Warning: (?P<summary>.+)$"),
        LatexMessageSeverity.WARNING,
    ),
    (
        re.compile(r"^pdfTeX warning (?P<summary>.+)$", re.I),
        LatexMessageSeverity.WARNING,
    ),
    (
        re.compile(r"^Overfull \\hbox (?P<summary>.+)$"),
        LatexMessageSeverity.WARNING,
    ),
    (
        re.compile(r"^Underfull \\hbox (?P<summary>.+)$"),
        LatexMessageSeverity.WARNING,
    ),
    (
        re.compile(r"^Package (?P<context>\S+) Info: (?P<summary>.+)$"),
        LatexMessageSeverity.INFO,
    ),
    (
        re.compile(r"^Latexmk: (?P<summary>.+)$"),
        LatexMessageSeverity.INFO,
    ),
    (
        re.compile(r"^This is (?P<summary>.+)$"),
        LatexMessageSeverity.INFO,
    ),
    (
        re.compile(r"^Document Class: (?P<summary>.+)$"),
        LatexMessageSeverity.INFO,
    ),
    (
        re.compile(r"^Missing character:(?P<summary>.+)$", re.I),
        LatexMessageSeverity.WARNING,
    ),
]

_ERROR_CONTINUATIONS = (
    "Emergency stop.",
    "==> Fatal error occurred, no output PDF file produced!",
)

_HIGHLIGHT_PATTERN = re.compile(r"^\.*[A-Za-z0-9 ]+:")
_TEX_ASSIGN_PATTERN = re.compile(r"\b\\[A-Za-z@]+")
_STRING_LITERAL_PATTERN = re.compile(r"(['\"])(.*?)(\1)")
_PATH_LINE_PATTERN = re.compile(r"^(?:\./|\../|/|[A-Za-z]:\\\\).+")
_PATH_FRAGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._:/\\-]+$")


class LatexLogParser:
    """Incrementally parse LaTeX output into structured messages."""

    def __init__(self) -> None:
        self._current: LatexMessage | None = None
        self._messages: list[LatexMessage] = []
        self._depth: int = 0

    @property
    def messages(self) -> Sequence[LatexMessage]:
        """Return the messages accumulated so far."""
        return tuple(self._messages)

    def process_line(self, line: str) -> list[LatexMessage]:
        """Process a log line and return messages that have just completed."""
        completed: list[LatexMessage] = []
        segments = self._consume_structure(line)
        if not segments:
            return completed

        for indent_level, payload in segments:
            if not payload or self._should_ignore(payload):
                continue

            severity, summary = self._match_message(payload)
            if severity is not None:
                message_summary = summary if summary else payload
                if (
                    severity is LatexMessageSeverity.ERROR
                    and message_summary in _ERROR_CONTINUATIONS
                    and self._current
                    and self._current.severity is LatexMessageSeverity.ERROR
                ):
                    self._current.details.append(message_summary)
                    continue
                completed.extend(self._finalize_current())
                self._current = LatexMessage(
                    severity=severity,
                    summary=message_summary,
                    indent=indent_level,
                )
                continue

            if self._current and self._is_detail_line(payload):
                self._current.details.append(payload)
                continue

            if self._current and self._merge_path_continuation(payload):
                continue

            if self._current and self._merge_text_continuation(payload, indent_level):
                continue

            completed.extend(self._finalize_current())
            self._current = LatexMessage(
                severity=LatexMessageSeverity.INFO,
                summary=payload,
                indent=indent_level,
            )

        return completed

    def finalize(self) -> list[LatexMessage]:
        """Flush any pending message."""
        return self._finalize_current()

    def _finalize_current(self) -> list[LatexMessage]:
        if not self._current:
            return []
        current, self._current = self._current, None
        self._messages.append(current)
        return [current]

    def _consume_structure(self, line: str) -> list[tuple[int, str]]:
        raw = line.rstrip("\r\n")
        if not raw.strip():
            return []

        depth = self._depth
        segments: list[tuple[int, str]] = []
        current_chars: list[str] = []
        message_started = False
        message_paren_balance = 0
        indent_for_segment = depth

        def flush() -> None:
            nonlocal current_chars, message_started, message_paren_balance, indent_for_segment
            if current_chars:
                payload = "".join(current_chars).strip()
                if payload:
                    segments.append((indent_for_segment, payload))
            current_chars = []
            message_started = False
            message_paren_balance = 0
            indent_for_segment = depth

        def peek_next_nonspace(index: int) -> str | None:
            while index < len(raw):
                ch = raw[index]
                if not ch.isspace():
                    return ch
                index += 1
            return None

        idx = 0
        while idx < len(raw):
            ch = raw[idx]

            if ch == "(":
                if message_started:
                    next_ch = peek_next_nonspace(idx + 1)
                    if message_paren_balance > 0 or (next_ch and next_ch not in {"/", ".", "\\"}):
                        message_paren_balance += 1
                        current_chars.append(ch)
                    else:
                        flush()
                        depth += 1
                        indent_for_segment = depth
                else:
                    depth += 1
                    indent_for_segment = depth
                idx += 1
                continue

            if ch == ")":
                if message_started:
                    if message_paren_balance > 0:
                        message_paren_balance -= 1
                        current_chars.append(ch)
                    else:
                        flush()
                        depth = max(depth - 1, 0)
                        indent_for_segment = depth
                else:
                    depth = max(depth - 1, 0)
                    indent_for_segment = depth
                idx += 1
                continue

            if ch.isspace():
                if message_started:
                    current_chars.append(ch)
                idx += 1
                continue

            if not message_started:
                message_started = True
                indent_for_segment = depth
            current_chars.append(ch)
            idx += 1

        flush()
        self._depth = depth
        return segments

    @staticmethod
    def _is_path_message(text: str) -> bool:
        return bool(_PATH_LINE_PATTERN.match(text))

    @staticmethod
    def _is_path_continuation_text(text: str) -> bool:
        if not text:
            return False
        stripped = text.lstrip()
        if not stripped:
            return False
        if stripped.startswith(("/", "./", "../")):
            return False
        if stripped.startswith(("Package ", "Class ", "LaTeX ", "Document ", "Library ", "File ")):
            return False
        if stripped.startswith(("! ", "*")):
            return False
        if ":" in stripped:
            return False
        if stripped.startswith(("x)) ", ")) ", "x))(", "))(")):
            return True
        if " " in stripped:
            return False
        return all(ch.isalnum() or ch in "._-" for ch in stripped)

    def _merge_path_continuation(self, payload: str) -> bool:
        if not self._current or self._current.severity is not LatexMessageSeverity.INFO:
            return False
        if not self._is_path_message(self._current.summary):
            return False
        if not self._is_path_continuation_text(payload):
            return False
        self._current.summary += payload.lstrip()
        return True

    def _merge_text_continuation(self, payload: str, indent: int) -> bool:
        if not self._current:
            return False
        if indent != self._current.indent:
            return False
        text = payload.strip()
        if not text:
            return False
        if self._is_path_message(text):
            return False
        if _HIGHLIGHT_PATTERN.match(text) and not text.startswith(
            ("T:", "OT:", "LT:", "pt:", "mm:", "in:")
        ):
            return False
        if len(text) > 48:
            return False

        summary = self._current.summary
        if not self._looks_like_soft_wrap(summary, text):
            return False

        joiner = ""
        if summary and not summary.endswith((" ", "/", "-", "'", "(", "[")):
            if (
                text.startswith(tuple(".,;:!?)]"))
                or text[0] == "'"
                or (summary.endswith(tuple("0123456789")) and text[0].isdigit())
            ):
                joiner = ""
            else:
                joiner = " "
        self._current.summary = summary + joiner + text
        return True

    @staticmethod
    def _looks_like_soft_wrap(summary: str, fragment: str) -> bool:
        if not summary:
            return False
        if fragment.startswith(("Run number", "Rule ", "Package", "Class", "LaTeX ", "Document ")):
            return False
        if fragment.startswith(("(", "[", "---")):
            return False
        if fragment.startswith(("/", "./", "../")):
            return False
        if fragment.startswith("latexmk"):
            return False
        if fragment.startswith("! "):
            return False
        if ":" in fragment and not fragment.startswith(("T:", "OT:", "pt:", "mm:", "in:")):
            return False

        stripped = fragment.strip()
        if not stripped:
            return False
        if stripped.isdigit():
            trimmed_summary = summary.rstrip()
            return trimmed_summary.endswith(tuple("0123456789")) or trimmed_summary.endswith("line")
        if stripped.replace(".", "").isdigit():
            trimmed_summary = summary.rstrip()
            return trimmed_summary.endswith(tuple("0123456789")) or trimmed_summary.endswith("line")
        if len(stripped) <= 4 and stripped.islower():
            return True
        if len(stripped) <= 4 and stripped in {".", "..", "...", ",", ";", "pt", "pt."}:
            return True
        if summary.endswith(("/", "-", "=")):
            return True
        if len(stripped) == 1 and stripped.isalpha():
            return True
        if stripped.startswith("T:") and len(summary) >= 2 and summary[-2] == "/":
            return True
        if stripped.startswith(("OT:", "LT:")) and len(summary) >= 2 and summary[-2] == "/":
            return True
        return len(stripped) <= 6 and stripped.isalpha()

    @staticmethod
    def _is_detail_line(line: str) -> bool:
        detail_prefixes = (
            "Type ",
            "Enter file name",
            "or enter new name",
            "<read ",
            "*** ",
            "l.",
        )
        return line.startswith(detail_prefixes) or (line.startswith(" ") and bool(line.strip()))

    @staticmethod
    def _should_ignore(line: str) -> bool:
        trimmed = line.strip()
        return (
            not trimmed
            or trimmed.startswith("[")
            or trimmed in {"Output written on", "Transcript written on"}
        )

    @staticmethod
    def _match_message(
        line: str,
    ) -> tuple[LatexMessageSeverity | None, str | None]:
        for pattern, severity in _MESSAGE_PATTERNS:
            match = pattern.match(line)
            if match:
                summary = match.groupdict().get("summary", "").strip()
                if not summary:
                    summary = line.strip()
                return severity, summary
        return None, None


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


@dataclass(slots=True)
class LatexStreamResult:
    """Result of streaming LaTeX engine output."""

    returncode: int
    messages: list[LatexMessage]


def _is_library_message(message: LatexMessage) -> bool:
    if message.severity is not LatexMessageSeverity.INFO:
        return False
    summary = message.summary.strip()
    return summary.startswith("Library (")


def _is_quiet_info_message(message: LatexMessage) -> bool:
    if message.severity is not LatexMessageSeverity.INFO:
        return False
    summary = message.summary.strip()
    if summary.startswith("Library ("):
        return True
    candidate = summary
    if candidate:
        candidate = candidate.replace("<", "").replace(">", "").strip()
    return bool(
        _PATH_LINE_PATTERN.match(candidate)
        or ("/" in candidate and _PATH_FRAGMENT_PATTERN.match(candidate))
    )


def _should_emit_message(message: LatexMessage, verbosity: int) -> bool:
    return not (verbosity <= 0 and _is_quiet_info_message(message))


def stream_latexmk_output(
    command: Sequence[str],
    *,
    cwd: str,
    env: Mapping[str, str],
    console: Console,
    verbosity: int = 0,
) -> LatexStreamResult:
    """Execute a LaTeX engine command and render output incrementally."""
    parser = LatexLogParser()
    renderer = LatexLogRenderer(console)

    with subprocess.Popen(
        command,
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    ) as process:
        selector = selectors.DefaultSelector()
        if process.stdout:
            selector.register(process.stdout, selectors.EVENT_READ)
        if process.stderr:
            selector.register(process.stderr, selectors.EVENT_READ)

        while selector.get_map():
            for key, _ in selector.select():
                stream_obj = key.fileobj
                if isinstance(stream_obj, int) or not hasattr(stream_obj, "readline"):
                    selector.unregister(stream_obj)
                    continue
                stream = cast(TextIO, stream_obj)
                chunk = stream.readline()
                if chunk:
                    for completed in parser.process_line(chunk):
                        if _should_emit_message(completed, verbosity):
                            renderer.consume(completed)
                else:
                    selector.unregister(stream)

        for completed in parser.finalize():
            if _should_emit_message(completed, verbosity):
                renderer.consume(completed)

        returncode = process.wait()

    renderer.summarize()
    return LatexStreamResult(returncode=returncode, messages=renderer.messages)


def parse_latex_log(log_path: Path) -> list[LatexMessage]:
    """Parse a LaTeX log file into structured messages."""
    if not log_path.exists():
        return []
    parser = LatexLogParser()
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parser.process_line(line)
    parser.finalize()
    return list(parser.messages)
