from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LATEX_LOG_PATH = (
    PROJECT_ROOT / "src" / "texsmith" / "adapters" / "latex" / "engines" / "latex" / "log.py"
)

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
    rich_module.__spec__ = importlib.machinery.ModuleSpec("rich", loader=None)

spec = importlib.util.spec_from_file_location(
    "texsmith.adapters.latex.engines.latex.log", LATEX_LOG_PATH
)
assert spec is not None and spec.loader is not None
latex_log = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = latex_log
spec.loader.exec_module(latex_log)

LatexLogParser = latex_log.LatexLogParser
LatexMessageSeverity = latex_log.LatexMessageSeverity
LatexMessage = latex_log.LatexMessage


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
        "LaTeX Warning: Reference `melting-behavior' on page 2 undefined on input line 2\n",
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


def test_parser_classifies_package_warning_with_details() -> None:
    parser = LatexLogParser()
    lines = [
        "Package fancyhdr Warning: \\headheight is too small (12.0pt).\n",
        "Type  <return> to proceed.\n",
    ]
    for line in lines:
        parser.process_line(line)
    parser.finalize()
    assert len(parser.messages) == 1
    warning = parser.messages[0]
    assert warning.severity is LatexMessageSeverity.WARNING
    assert warning.summary == "\\headheight is too small (12.0pt)."
    assert "Type  <return> to proceed." in warning.details


def test_parser_drops_progress_and_transcript_lines() -> None:
    parser = LatexLogParser()
    lines = [
        "[1]\n",
        "[2]\n",
        "Output written on\n",
        "Transcript written on\n",
    ]
    for line in lines:
        parser.process_line(line)
    parser.finalize()
    assert list(parser.messages) == []


def test_parser_classifies_latexmk_errors() -> None:
    parser = LatexLogParser()
    lines = [
        "Latexmk: applying rule 'pdflatex'...\n",
        "Latexmk: Rule 'pdflatex' has failed\n",
        "Latexmk: Errors, so I did not complete processing of 'main.tex'\n",
    ]
    for line in lines:
        parser.process_line(line)
    parser.finalize()
    severities = [message.severity for message in parser.messages]
    assert severities == [
        LatexMessageSeverity.INFO,
        LatexMessageSeverity.ERROR,
        LatexMessageSeverity.ERROR,
    ]


def test_should_emit_message_filters_library_info() -> None:
    quiet_message = LatexMessage(
        severity=LatexMessageSeverity.INFO,
        summary="Library (tcolorbox): 'tcbskins.code.tex' version '6.2.0'",
    )
    assert latex_log._should_emit_message(quiet_message, verbosity=0) is False
    assert latex_log._should_emit_message(quiet_message, verbosity=1) is True

    path_message = LatexMessage(
        severity=LatexMessageSeverity.INFO,
        summary="/usr/share/texlive/texmf-dist/tex/latex/pgf/frontendlayer/tikz.sty",
    )
    assert latex_log._should_emit_message(path_message, verbosity=0) is False
    assert latex_log._should_emit_message(path_message, verbosity=1) is True

    bracketed_path_message = LatexMessage(
        severity=LatexMessageSeverity.INFO,
        summary="<./assets/figure.pdf>",
    )
    assert latex_log._should_emit_message(bracketed_path_message, verbosity=0) is False
    assert latex_log._should_emit_message(bracketed_path_message, verbosity=1) is True

    fragment_message = LatexMessage(
        severity=LatexMessageSeverity.INFO,
        summary="texmf-dist/tex/latex/base/article.cls",
    )
    assert latex_log._should_emit_message(fragment_message, verbosity=0) is False
    assert latex_log._should_emit_message(fragment_message, verbosity=1) is True

    info_message = LatexMessage(
        severity=LatexMessageSeverity.INFO,
        summary="Document Class: article",
    )
    assert latex_log._should_emit_message(info_message, verbosity=0) is True
