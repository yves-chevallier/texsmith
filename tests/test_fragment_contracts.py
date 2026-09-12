"""The fragment contracts (specs/migration/fragment-contracts.md, sections 1 to 5).

Every ``provides`` entry of ``tmark.fragments()`` must be defined by its
fragment's ``.sty``; ``activate_from_requires`` maps a writer's ``Requires``
onto the active fragments; and a standalone document exercising every
contract macro once (the invocations of the writer snapshots) builds with
tectonic when the engine can be provisioned. The Typst mirror
(``texsmith.typ``) compiles with the ``typst`` package when it is installed.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import re
import shutil

import pytest

from texsmith.core.callouts import DEFAULT_CALLOUTS, normalise_callouts
from texsmith.core.fragments import (
    FRAGMENT_REGISTRY,
    BaseFragment,
    FragmentDefinition,
    render_fragments,
)
from texsmith.core.fragments.contracts import (
    fragment_contract,
    fragment_contracts,
)
from texsmith.core.fragments.resolution import (
    ACTIVE_FRAGMENTS_KEY,
    REQUIRES_PACKAGES_KEY,
    activate_from_requires,
    contract_active,
    extra_packages_from_requires,
    inject_requires,
)
from texsmith.core.templates.typst import TYPST_LIBRARY_PATH, copy_typst_library


CONTRACT_FRAGMENTS = [
    "ts-typesetting",
    "ts-callouts",
    "ts-code",
    "ts-keystrokes",
    "ts-todolist",
    "ts-glossary",
    "ts-index",
    "ts-bibliography",
    "ts-fonts",
    "ts-critic",
]

# A 1x1 white PNG for \tsicon / #ts-icon.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


# --------------------------------------------------------------------------
# Static: every provides entry is a definition in the fragment's templates
# --------------------------------------------------------------------------


def _fragment_sources(name: str) -> str:
    fragment = FRAGMENT_REGISTRY.resolve(name)
    assert isinstance(fragment, (BaseFragment, FragmentDefinition))
    return "\n".join(piece.template_path.read_text(encoding="utf-8") for piece in fragment.pieces)


def _defines(source: str, entry: str) -> bool:
    if entry.startswith("\\"):
        name = re.escape(entry[1:])
        pattern = (
            r"\\(?:New|Provide|Declare)DocumentCommand\s*\{?\s*\\" + name + r"\s*\}?\s*\{"
            r"|\\(?:new|provide)command\*?\s*\{?\\" + name + r"\}?"
        )
    else:
        name = re.escape(entry)
        pattern = (
            r"\\NewDocumentEnvironment\s*\{" + name + r"\}"
            r"|\\newtcolorbox(?:\[[^\]]*\])?\s*\{" + name + r"\}"
            r"|\\newtcblisting(?:\[[^\]]*\])?\s*\{" + name + r"\}"
            r"|\\newlist\s*\{" + name + r"\}"
            r"|\\newenvironment\s*\{" + name + r"\}"
        )
    return re.search(pattern, source) is not None


@pytest.mark.parametrize("name", CONTRACT_FRAGMENTS)
def test_every_provides_entry_is_defined(name: str) -> None:
    row = fragment_contract(name)
    assert row is not None, f"{name} is not a row of tmark.fragments()"
    source = _fragment_sources(name)
    missing = [entry for entry in row.provides if not _defines(source, entry)]
    assert not missing, f"{name} does not define {missing}"


def test_contract_rows_with_a_fragment_are_all_covered() -> None:
    """A new row of ``FRAGMENTS`` with a bundled fragment must join the list."""
    registered = set(FRAGMENT_REGISTRY.default_fragment_names)
    for row in fragment_contracts():
        if row.provides and row.name in registered:
            assert row.name in CONTRACT_FRAGMENTS, row.name


def test_provides_are_unique_across_rows() -> None:
    seen: set[str] = set()
    for row in fragment_contracts():
        for entry in row.provides:
            assert entry not in seen, entry
            seen.add(entry)


# --------------------------------------------------------------------------
# Activation from Requires (§2)
# --------------------------------------------------------------------------


def test_activate_from_requires_follows_the_table() -> None:
    requires = {
        "packages": ["csquotes", "ulem"],
        "fragments": ["ts-callouts", "ts-code", "ts-typesetting"],
        "shell_escape": False,
        "bibliography": False,
        "citations": [],
        "acronyms": [],
        "index": [],
        "counters": [],
    }
    active = activate_from_requires(requires)
    assert {"ts-callouts", "ts-code", "ts-typesetting", "ts-fonts", "ts-extra"} == active

    assert "ts-index" in activate_from_requires({"index": ["physics"]})
    assert "ts-bibliography" in activate_from_requires({"bibliography": True})
    assert "ts-bibliography" in activate_from_requires({"citations": ["knuth"]})
    assert "ts-glossary" in activate_from_requires({"acronyms": ["HTML"]})
    assert "ts-glossary" in activate_from_requires({}, front_matter={"glossary": True})
    assert "ts-glossary" in activate_from_requires(
        {}, front_matter={"press": {"acronyms": {"A": "a"}}}
    )
    assert "ts-geometry" not in activate_from_requires({})
    assert activate_from_requires(None) == {"ts-fonts", "ts-extra"}


def test_extra_packages_merge_requires_and_implied_rows() -> None:
    packages = extra_packages_from_requires(
        {"packages": ["csquotes", "ulem"], "fragments": ["ts-keystrokes"]}
    )
    assert packages[:2] == ["csquotes", "ulem"]
    assert "tikz" in packages
    assert "fontspec" in packages  # implied by ts-fonts, always active
    assert len(packages) == len(set(packages))


def test_inject_requires_populates_the_context() -> None:
    context: dict[str, object] = {}
    active = inject_requires(
        context, {"fragments": ["ts-code"], "index": ["physics"], "shell_escape": True}
    )
    assert "ts-index" in active
    assert context[ACTIVE_FRAGMENTS_KEY] == sorted(active)
    assert "fvextra" in context[REQUIRES_PACKAGES_KEY]
    assert context["index_registries"] == ["physics"]
    assert context["requires_shell_escape"] is True
    assert contract_active(context, "ts-code") is True
    assert contract_active(context, "ts-callouts") is False
    assert contract_active({}, "ts-code") is None


def test_contract_fragments_honour_the_activation_set(tmp_path: Path) -> None:
    """With an activation set the sniffers are bypassed in both directions."""
    context = _contract_context(tmp_path, active=["ts-callouts"])
    context["mainmatter"] = "\\keystroke{Ctrl} \\begin{code}{py}{}{}x\\end{code}"
    result = render_fragments(
        ["ts-callouts", "ts-keystrokes", "ts-code", "ts-typesetting"],
        context=context,
        output_dir=tmp_path / "out",
    )
    assert "ts-callouts" in result.packages
    assert "ts-keystrokes" not in result.packages
    assert "ts-code" not in result.packages
    assert "ts-typesetting" not in result.packages


def test_typesetting_sty_only_on_the_contract_path(tmp_path: Path) -> None:
    legacy: dict[str, object] = {"output_dir": str(tmp_path)}
    result = render_fragments(
        ["ts-typesetting"],
        context=legacy,
        output_dir=tmp_path / "a",
        overrides={"typesetting": {"leading": "double"}},
    )
    assert result.packages == []
    assert any("Double" in s for s in result.variable_injections["extra_packages"])

    contract = _contract_context(tmp_path, active=["ts-typesetting"])
    result = render_fragments(["ts-typesetting"], context=contract, output_dir=tmp_path / "b")
    assert result.packages == ["ts-typesetting"]
    sty = (tmp_path / "b" / "ts-typesetting.sty").read_text(encoding="utf-8")
    for macro in ("\\tslead", "\\tsmark", "\\tsdivider", "\\tsepigraph", "\\tsaside"):
        assert f"\\NewDocumentCommand{{{macro}}}" in sty
    assert "\\NewDocumentEnvironment{tsdiv}" in sty


# --------------------------------------------------------------------------
# Deprecations (§4)
# --------------------------------------------------------------------------


def test_book_and_letter_redefine_after_extra_packages() -> None:
    from texsmith.templates import book, letter

    book_tex = (Path(book.__file__).parent / "template" / "template.tex").read_text()
    assert book_tex.index("\\VAR{extra_packages}") < book_tex.index(
        "\\RenewDocumentCommand{\\tscodeinline}"
    )
    letter_tex = (Path(letter.__file__).parent / "template" / "template.tex").read_text()
    assert letter_tex.index("\\VAR{extra_packages}") < letter_tex.index("/ts/callout/.append style")


# --------------------------------------------------------------------------
# Compile: every contract macro once, with tectonic
# --------------------------------------------------------------------------


def _pygments_style_defs() -> str | None:
    try:
        from pygments.formatters import LatexFormatter
    except Exception:  # pragma: no cover - pygments is a dependency
        return None
    return LatexFormatter(style="bw").get_style_defs()


def _contract_context(tmp_path: Path, *, active: list[str]) -> dict[str, object]:
    requires = {
        "packages": ["csquotes", "ulem", "graphicx", "hyperref", "enumitem"],
        "fragments": [name for name in active if name != "ts-extra"],
        "shell_escape": False,
        "bibliography": False,
        "citations": ["knuth"] if "ts-bibliography" in active else [],
        "acronyms": ["HTML"] if "ts-glossary" in active else [],
        "index": ["physics"] if "ts-index" in active else [],
        "counters": [],
    }
    context: dict[str, object] = {
        "output_dir": str(tmp_path),
        "latex_engine": "xelatex",
        "callouts_definitions": normalise_callouts(dict(DEFAULT_CALLOUTS)),
        "acronyms": {"HTML": ("HTML", "HyperText Markup Language")},
        "citations": [],
        "bibliography_entries": {},
        "code": {"engine": "pygments", "style": "bw"},
        "fonts": {"family": "lm"},
        "ts_extra_disable_hyperref": True,
    }
    defs = _pygments_style_defs()
    if defs:
        context["pygments_style_defs"] = defs
    inject_requires(context, requires)
    context[ACTIVE_FRAGMENTS_KEY] = sorted(set(active))
    return context


CONTRACT_BODY = r"""
\section{Contracts}\label{sec:intro}

\tslead{Lead} A \tsmark{mark} and \tskeys{Ctrl,Alt,Del} and \tskeys{Ctrl,{,}} and
\tskeys{ctrl,arrow-up}. The \tsacr{HTML} spec and \tsacr{HTML} again.
Bytes\tsindex{endianness} and\tsindex{byte order!endianness} and\tsindex[main]{chocolate}
and\tsindex[registry=physics]{Einstein}. Hooke's law\tsaside[side=left]{linear only at
small strain} holds\tsaside{on the right}. \tsscript{arabic}{x} \tsemoji{!}
Inline \tscodeinline[lang=py]{xs\allowbreak{}.sort()} and \tscodeinline{a\_b}.
Logos: \tslogo{XeLaTeX}, \tslogo{pdfTeX}, \tslogo{BibLaTeX}, \tslogo{ConTeXt}, \tslogo{Nope}.
\tsins{new} \tsdel{old} \tssubst{old}{new} \tscomment{a comment}.
See \textcite{knuth} and \parencite[p.~3]{knuth} and \citeyear{knuth}.
\tsicon{icon.png}

\tsepigraph[source={Someone}]{A quote.}
\tsepigraph{A quote without source.}

\tsprogress[thin]{0.45}{label}
\tsprogress{0.7}{full}

\begin{tscallout}[kind=warning, title={LaTeX toolchain}]
Install TeX Live before \tscodeinline{texsmith --build}.
\end{tscallout}

\begin{tscallout}[kind=tip]
No title: the kind's word.
\end{tscallout}

\begin{tscallout}[kind=note, title={Folded}, id=note1, class={wide}, collapsed, cols=2]
Attributes forwarded as keys.
\end{tscallout}

\begin{tscallout}[kind=seealso]
Alias.
\end{tscallout}

\begin{tscallout}[kind=nosuchkind]
Falls back to default.
\end{tscallout}

\begin{tstasklist}
\item[\tsdone] done
\item[\tstodo] open
\item[\tspartial] half
\end{tstasklist}

\begin{tscode}[lang=python, title={bubble\_sort.py}, linenums, hl_lines={2-3}, id=lst:bubble, caption={Bubble sort, naive version.}]
def bubble(xs):
    return sorted(xs)  # {braces} and \backslash and %percent
\end{tscode}

\begin{tscode}
[1, 2, 3]
\end{tscode}

\begin{tscode}[lang=yaml table]
a: 1
\end{tscode}

\begin{tscode}[lang=md, class={snippet}, caption={A title}, width={60\%}]
# Hello
\end{tscode}

\begin{tscode}[lang=python, title={hanoi.py}, class={wide}, stretch=0.5, linenums=5]
print(1)
\end{tscode}

\begin{tsdiv}{gadget}[x=1]
Transparent container.
\end{tsdiv}

\begin{tsdiv}{multicolumn}[cols=2]
Two columns of text, two columns of text, two columns of text, two columns
of text, two columns of text, two columns of text, two columns of text.
\end{tsdiv}

\begin{tsdiv}{tab}[title={Tab title}]
Tab body.
\end{tsdiv}

\tsdivider

Listing \ref{lst:bubble}, note \ref{note1}.

\begin{thebibliography}{1}
\bibitem{knuth} D. Knuth, The \TeX book.
\end{thebibliography}
"""

PYGMENTS_BODY = r"""
\begin{tscode}[lang=python, engine=pygments, id=lst:py]
\PY{k}{def} \PY{n+nf}{f}\PY{p}{(}\PY{p}{)}\PY{p}{:} \PY{k}{pass}
\end{tscode}
"""


def _write_contract_document(build: Path) -> Path:
    context = _contract_context(build, active=[*CONTRACT_FRAGMENTS, "ts-extra"])
    names = [
        "ts-typesetting",
        "ts-fonts",
        "ts-extra",
        "ts-keystrokes",
        "ts-callouts",
        "ts-code",
        "ts-glossary",
        "ts-index",
        "ts-bibliography",
        "ts-todolist",
        "ts-critic",
    ]
    result = render_fragments(names, context=context, output_dir=build)
    for name in CONTRACT_FRAGMENTS:
        if name != "ts-bibliography":
            assert name in result.packages, f"{name} did not render"
    preamble = "\n".join(result.variable_injections.get("extra_packages", []))
    backmatter = "\n".join(result.variable_injections.get("fragment_backmatter", []))
    body = CONTRACT_BODY
    if "pygments_style_defs" in context:
        body += PYGMENTS_BODY
    (build / "icon.png").write_bytes(_PNG)
    tex = (
        "\\documentclass{article}\n"
        "\\usepackage[svgnames,dvipsnames,x11names]{xcolor}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage[english]{babel}\n"
        "\\usepackage[colorlinks=true]{hyperref}\n"
        f"{preamble}\n"
        "\\begin{document}\n"
        f"{body}\n"
        f"{backmatter}\n"
        "\\end{document}\n"
    )
    main = build / "contracts.tex"
    main.write_text(tex, encoding="utf-8")
    return main


def test_contract_document_renders_every_fragment(tmp_path: Path) -> None:
    main = _write_contract_document(tmp_path)
    tex = main.read_text(encoding="utf-8")
    for name in CONTRACT_FRAGMENTS:
        if name != "ts-bibliography":
            assert f"\\usepackage{{{name}}}" in tex
            assert (tmp_path / f"{name}.sty").exists()
    assert "\\ProvideDocumentCommand{\\textcite}" in tex
    assert "\\usepackage[normalem]{ulem}" in tex
    assert "\\usepackage{glossaries}" not in tex  # the fragment loads it with options
    index_sty = (tmp_path / "ts-index.sty").read_text(encoding="utf-8")
    assert "\\makeindex[name=physics" in index_sty
    keys_sty = (tmp_path / "ts-keystrokes.sty").read_text(encoding="utf-8")
    assert "ts@key@ctrl" in keys_sty


def _tectonic_binary() -> Path | None:
    from texsmith.adapters.latex.tectonic import (
        BundledToolError,
        _install_dir,
        select_tectonic_binary,
    )

    bundled = _install_dir() / "tectonic"
    system = shutil.which("tectonic")
    if not bundled.exists() and system is None and not os.environ.get("CI"):
        return None
    try:
        return select_tectonic_binary().path
    except BundledToolError:
        return None
    except Exception:  # pragma: no cover - network failures
        return None


def test_contract_document_builds_with_tectonic(tmp_path: Path) -> None:
    binary = _tectonic_binary()
    if binary is None:
        pytest.skip("tectonic cannot be provisioned")
    from texsmith.adapters.latex.engines import (
        EngineChoice,
        EngineFeatures,
        build_engine_command,
        build_tex_env,
        run_engine_command,
    )

    main = _write_contract_document(tmp_path)
    features = EngineFeatures(
        requires_shell_escape=False, bibliography=False, has_index=False, has_glossary=False
    )
    command = build_engine_command(
        EngineChoice(backend="tectonic", latexmk_engine=None),
        features,
        main_tex_path=main,
        tectonic_binary=binary,
    )
    env = build_tex_env(tmp_path, isolate_cache=False)
    result = run_engine_command(
        command,
        backend="tectonic",
        workdir=tmp_path,
        env=env,
        console=None,
        features=features,
        rerun_limit=3,
    )
    log = (
        command.log_path.read_text(encoding="utf-8", errors="replace")
        if command.log_path.exists()
        else ""
    )
    errors = "\n".join(line for line in log.splitlines() if line.startswith("!"))
    assert result.returncode == 0, f"tectonic failed:\n{errors}\n{log[-3000:]}"
    assert command.pdf_path.exists()
    assert command.pdf_path.read_bytes().startswith(b"%PDF")


# --------------------------------------------------------------------------
# Typst mirror
# --------------------------------------------------------------------------

TYPST_BODY = """#import "texsmith.typ": *

= Contracts <sec:intro>

#ts-lead[Lead] A #highlight[mark] and #ts-keys("Ctrl", "Alt", "Del"). The #ts-acr("HTML")
spec and #ts-gls("term"). Bytes#ts-index([endianness]) and#ts-index([byte order], [endianness])
and#ts-index([chocolate], main: true)#ts-index([Einstein], registry: "physics").
Hooke's law#ts-aside(side: "left")[linear only] holds. #ts-script("arabic")[x] #ts-emoji[!]
Inline #ts-codeinline(lang: "py", "xs.sort()"). #ts-ins[new] #ts-del[old] #ts-subst[old][new]
#ts-comment[a comment]. Page #ts-page(<sec:intro>). #ts-icon("icon.png")

#ts-epigraph(source: [Someone])[A quote.]
#ts-epigraph[A quote without source.]

#ts-progress(0.45, label: "label", thin: true)
#ts-progress(0.7, "full")

#ts-callout(kind: "warning", title: [LaTeX toolchain])[
Install TeX Live.
]
#ts-callout(kind: "tip", collapsed: false)[No title.]
#ts-callout(kind: "note", title: [Folded], id: "note1", class: ("wide",), collapsed: true, cols: 2)[
Attributes.
]
#ts-callout(kind: "nosuchkind")[Default.]

- #ts-task("done")[done]
- #ts-task("open")[open]
- #ts-task("partial")[half]

#ts-code(title: [bubble\\_sort.py], linenums: 1, hl-lines: ("2-3",), id: "lst:bubble", caption: [Bubble sort.])[
```python
def bubble(xs): pass
```
]
#ts-code(class: ("snippet",), caption: "A title", width: "60%")[
```md
# Hello
```
]

#ts-div("gadget", x: 1)[Transparent.]
#ts-div("multicolumn", cols: 2)[Two columns of text, two columns of text, two columns of text.]
#ts-div("tab", title: [Tab title])[Tab body.]

#ts-divider()

Listing @lst:bubble.
"""


def test_typst_library_exists_and_names_every_contract() -> None:
    source = TYPST_LIBRARY_PATH.read_text(encoding="utf-8")
    for name in (
        "ts-lead",
        "ts-divider",
        "ts-epigraph",
        "ts-aside",
        "ts-progress",
        "ts-icon",
        "ts-div",
        "ts-callout",
        "ts-code",
        "ts-codeinline",
        "ts-keys",
        "ts-task",
        "ts-gls",
        "ts-acr",
        "ts-index",
        "ts-page",
        "ts-script",
        "ts-emoji",
        "ts-ins",
        "ts-del",
        "ts-subst",
        "ts-comment",
    ):
        assert re.search(r"#let " + re.escape(name) + r"\(", source), name


def test_typst_library_compiles(tmp_path: Path) -> None:
    from texsmith.writers.typst import build

    if not build._package_available():
        pytest.skip("typst package not installed")
    copy_typst_library(tmp_path)
    (tmp_path / "icon.png").write_bytes(_PNG)
    source = tmp_path / "doc.typ"
    source.write_text(TYPST_BODY, encoding="utf-8")
    result = build._compile_with_package(source, tmp_path / "doc.pdf")
    assert result.ok, result.message
    assert result.pdf_path is not None
    assert result.pdf_path.read_bytes().startswith(b"%PDF")
