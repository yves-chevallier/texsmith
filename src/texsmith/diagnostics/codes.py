"""TeXSmith's diagnostic codes: default severity and a one-line description.

The identifiers are kebab-case like tmark's. Two kinds live here: TeXSmith's
own codes, which must not shadow a tmark id (``tests/test_diagnostics_codes.py``
checks that against a vendored copy of tmark's list), and codes that
deliberately **reuse** a tmark id because the finding is the same one tmark
will report once the corresponding stage moves to Rust (``tmark=True``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Severity


#: The free-form code of the legacy ``DiagnosticEmitter.warning()``/``error()``
#: messages: engine, network and template messages that carry no location.
LEGACY_CODE = "texsmith"


@dataclass(frozen=True, slots=True)
class CodeInfo:
    code: str
    severity: Severity
    doc: str
    #: ``True`` when the id is tmark's, reused on purpose.
    tmark: bool = False


_TABLE: tuple[CodeInfo, ...] = (
    CodeInfo(LEGACY_CODE, Severity.WARNING, "A message without a code (engine, network, template)"),
    CodeInfo(
        "asset-missing",
        Severity.WARNING,
        "An image or file referenced by the document does not exist",
    ),
    CodeInfo(
        "asset-convert-failed",
        Severity.WARNING,
        "A diagram or image could not be converted; the node is kept as a literal",
    ),
    CodeInfo(
        "doi-fetch-failed", Severity.WARNING, "A DOI could not be resolved to a bibliography entry"
    ),
    CodeInfo(
        "snippet-build-failed",
        Severity.WARNING,
        "An executed or rendered snippet failed; the fence is kept as code",
    ),
    CodeInfo(
        "reader-unsupported",
        Severity.WARNING,
        "An HTML construct the IR cannot express; kept as a generic Div or Span",
    ),
    CodeInfo(
        "reader-unprocessed-block",
        Severity.WARNING,
        "A '///' block marker Python-Markdown left as prose",
    ),
    CodeInfo("slot-missing", Severity.WARNING, "A slot selector matched no top-level heading"),
    CodeInfo(
        "slot-selector-unsupported",
        Severity.WARNING,
        "A slot selector uses a CSS form the IR does not support",
    ),
    CodeInfo(
        "slot-nested-heading",
        Severity.WARNING,
        "A slot selector matched a heading nested in a container",
    ),
    CodeInfo(
        "var-unresolved", Severity.WARNING, "A moustache names a path that no context defines"
    ),
    CodeInfo("var-not-scalar", Severity.WARNING, "A moustache resolves to a list or a mapping"),
    CodeInfo(
        "font-missing",
        Severity.WARNING,
        "A declared font family is unknown or could not be fetched",
    ),
    CodeInfo(
        "frontmatter-root-overrides-press",
        Severity.INFO,
        "A root key overrides the same key under press",
    ),
    CodeInfo(
        "file-unreadable", Severity.WARNING, "A file exists but cannot be read or decoded as UTF-8"
    ),
    CodeInfo("include-missing", Severity.WARNING, "An included file cannot be loaded", tmark=True),
    CodeInfo(
        "include-cycle",
        Severity.WARNING,
        "An include names a file that is already being included",
    ),
    CodeInfo(
        "deprecated-frontmatter-key",
        Severity.WARNING,
        "A deprecated front-matter spelling",
        tmark=True,
    ),
    CodeInfo(
        "crossref-inventory-missing",
        Severity.WARNING,
        "A cross-reference inventory cannot be loaded",
        tmark=True,
    ),
    CodeInfo(
        "crossref-inventory-stale",
        Severity.WARNING,
        "A cross-reference inventory no longer matches its source",
        tmark=True,
    ),
    CodeInfo(
        "ref-unresolved", Severity.WARNING, "A reference key found in no registry", tmark=True
    ),
    CodeInfo("label-duplicate", Severity.WARNING, "The same label defined twice", tmark=True),
)

CODES: dict[str, CodeInfo] = {info.code: info for info in _TABLE}


def default_severity(code: str) -> Severity:
    """The severity a code carries when the emitter names none.

    A code absent from the table (a tmark id not listed here) is a warning:
    tmark records arrive with their own severity anyway.
    """
    info = CODES.get(code)
    return info.severity if info is not None else Severity.WARNING


def own_codes() -> frozenset[str]:
    """TeXSmith's own identifiers, the ones that must not shadow tmark's."""
    return frozenset(info.code for info in _TABLE if not info.tmark)


def reused_tmark_codes() -> frozenset[str]:
    """The tmark identifiers TeXSmith emits itself."""
    return frozenset(info.code for info in _TABLE if info.tmark)


__all__ = [
    "CODES",
    "LEGACY_CODE",
    "CodeInfo",
    "default_severity",
    "own_codes",
    "reused_tmark_codes",
]
