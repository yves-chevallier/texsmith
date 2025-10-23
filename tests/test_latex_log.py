from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LATEX_LOG_PATH = PROJECT_ROOT / "src" / "texsmith" / "latex_log.py"

# Provide minimal stubs for optional dependencies required during import.
if "rich.console" not in sys.modules:
    rich_module = types.ModuleType("rich")
    rich_console_module = types.ModuleType("rich.console")
    rich_text_module = types.ModuleType("rich.text")

    class _StubConsole:  # pragma: no cover - placeholder
        def print(self, *_args: object, **_kwargs: object) -> None:
            pass

    class _StubText:  # pragma: no cover - placeholder
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.fragments: list[str] = []

        def append(self, text: str, **_kwargs: object) -> None:
            self.fragments.append(text)

        def __str__(self) -> str:
            return "".join(self.fragments)

    rich_console_module.Console = _StubConsole
    rich_text_module.Text = _StubText

    sys.modules["rich"] = rich_module
    sys.modules["rich.console"] = rich_console_module
    sys.modules["rich.text"] = rich_text_module

spec = importlib.util.spec_from_file_location("texsmith.latex_log", LATEX_LOG_PATH)
assert spec is not None and spec.loader is not None
latex_log = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = latex_log
spec.loader.exec_module(latex_log)

LatexLogParser = latex_log.LatexLogParser
LatexMessageSeverity = latex_log.LatexMessageSeverity


def test_parser_extracts_error_and_context() -> None:
    parser = LatexLogParser()
    log_path = Path("test-mdpi.log")
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            parser.process_line(line)
    parser.finalize()

    messages = list(parser.messages)
    error_messages = [
        message
        for message in messages
        if message.severity is LatexMessageSeverity.ERROR
    ]
    assert error_messages, "Expected to find at least one LaTeX error message"

    first_error = error_messages[0]
    assert "LaTeX Error" in first_error.summary
    assert "mdpi.cls" in first_error.summary

    joined_details = "\n".join(first_error.details)
    assert "Emergency stop." in joined_details
    assert "l.2 \\Title" in joined_details

    latex2e_messages = [
        message for message in messages if message.summary.startswith("LaTeX2e")
    ]
    assert latex2e_messages, "Expected to capture LaTeX2e banner"
    assert latex2e_messages[0].indent > 0


def test_parser_balances_parentheses_across_complex_log() -> None:
    parser = LatexLogParser()
    log_path = Path("examples/latexmk-output.log")
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            parser.process_line(line)
    parser.finalize()
    assert parser._depth == 0


def test_parser_merges_wrapped_paths() -> None:
    parser = LatexLogParser()
    lines = [
        "(/usr/share/texlive/texmf-dist/tex/generic/pgf/math/pgfmathfunctions.trigonomet\n",
        "ric.code.tex)) (/usr/share/texlive/texmf-dist/tex/latex/tools/verbatim.sty)\n",
    ]
    for line in lines:
        parser.process_line(line)
    parser.finalize()
    summaries = [message.summary for message in parser.messages]
    assert "ric.code.tex" not in summaries
    assert ".tex" not in summaries


def test_parser_merges_wrapped_warning_numbers() -> None:
    parser = LatexLogParser()
    lines = [
        "LaTeX Warning: Reference `melting-behavior' "
        "on page 2 undefined on input line 2\n",
        "86.\n",
    ]
    for line in lines:
        parser.process_line(line)
    parser.finalize()
    summaries = [message.summary for message in parser.messages]
    assert "286." in summaries[0]


def test_parser_merges_wrapped_input_line_suffix() -> None:
    parser = LatexLogParser()
    lines = [
        "Reference `mechanical-results' on page 3 undefined on input line\n",
        "321.\n",
    ]
    for line in lines:
        parser.process_line(line)
    parser.finalize()
    summaries = [message.summary for message in parser.messages]
    assert any(summary.endswith("line 321.") for summary in summaries)
