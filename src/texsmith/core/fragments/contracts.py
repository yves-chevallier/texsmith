"""The fragment-contract table and the partial → macro mapping.

``specs/migration/fragment-contracts.md`` §2 places the ``FRAGMENTS`` table
in ``tmark_ir::registry``; ``tmark.fragments()`` exposes it. This module reads
it when the wheel is importable and carries a vendored copy otherwise, so a
fragment can be validated and a deprecation message can name the replacement
macro of a partial without a hard dependency on the wheel.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FragmentContract:
    """One row of the ``FRAGMENTS`` table."""

    name: str
    #: Macros (``\`` prefix) and environments (bare) the fragment must define.
    provides: tuple[str, ...]
    #: LaTeX packages the contract implies (``tlmgr`` hints, ``ts-extra``).
    packages: tuple[str, ...]
    shell_escape: bool
    description: str


# Vendored copy of ``tmark_ir::registry::FRAGMENTS`` (fragment-contracts.md §2).
_VENDORED: tuple[FragmentContract, ...] = (
    FragmentContract(
        "ts-typesetting",
        (
            "\\tslead",
            "\\tsmark",
            "\\tsdivider",
            "\\tsepigraph",
            "\\tsaside",
            "\\tsprogress",
            "\\tsicon",
            "\\tslogo",
            "tsdiv",
        ),
        ("xcolor", "epigraph", "marginnote", "multicol", "progressbar", "graphicx"),
        False,
        "lead-ins, highlight, divider, epigraph, asides, progress bars, generic containers",
    ),
    FragmentContract(
        "ts-callouts",
        ("tscallout",),
        ("tcolorbox", "xcolor"),
        False,
        "admonitions and theorem boxes",
    ),
    FragmentContract(
        "ts-code",
        ("tscode", "\\tscodeinline"),
        ("tcolorbox", "fvextra"),
        False,
        "code listings; engine (minted/listings/verbatim/pygments) is the fragment's choice",
    ),
    FragmentContract("ts-keystrokes", ("\\tskeys",), ("tikz",), False, "keyboard keys"),
    FragmentContract(
        "ts-todolist",
        ("tstasklist", "\\tsdone", "\\tstodo", "\\tspartial"),
        ("enumitem", "amssymb", "pifont"),
        False,
        "task lists",
    ),
    FragmentContract(
        "ts-glossary", ("\\tsgls", "\\tsacr"), ("glossaries",), False, "glossary terms and acronyms"
    ),
    FragmentContract(
        "ts-index", ("\\tsindex",), ("imakeidx",), False, "index entries and registries"
    ),
    FragmentContract(
        "ts-bibliography",
        ("\\parencite", "\\textcite"),
        (),
        False,
        "citation fallbacks without biblatex",
    ),
    FragmentContract(
        "ts-fonts",
        ("\\tsscript", "\\tsemoji"),
        ("fontspec",),
        False,
        "script and emoji font switches",
    ),
    FragmentContract(
        "ts-critic",
        ("\\tsins", "\\tsdel", "\\tssubst", "\\tscomment"),
        ("ulem", "xcolor"),
        False,
        "critic markup (tmark M5)",
    ),
)


def _from_tmark() -> tuple[FragmentContract, ...] | None:
    try:
        import tmark  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - the wheel is optional at runtime
        return None
    try:
        rows = tmark.fragments()
    except Exception:  # pragma: no cover - defensive
        return None
    contracts: list[FragmentContract] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        contracts.append(
            FragmentContract(
                name=str(row.get("name", "")),
                provides=tuple(str(item) for item in row.get("provides", ())),
                packages=tuple(str(item) for item in row.get("packages", ())),
                shell_escape=bool(row.get("shell_escape", False)),
                description=str(row.get("description", "")),
            )
        )
    return tuple(contracts) or None


def fragment_contracts() -> tuple[FragmentContract, ...]:
    """Return the ``FRAGMENTS`` table, from ``tmark`` when importable."""
    return _from_tmark() or _VENDORED


def fragment_contract(name: str) -> FragmentContract | None:
    """Return the contract row named ``name``, if any."""
    for row in fragment_contracts():
        if row.name == name:
            return row
    return None


def contract_names() -> frozenset[str]:
    """Names of every contract row."""
    return frozenset(row.name for row in fragment_contracts())


def implied_packages(active: Iterable[str]) -> list[str]:
    """LaTeX packages implied by the active contract rows, first seen first."""
    names = set(active)
    seen: dict[str, None] = {}
    for row in fragment_contracts():
        if row.name not in names:
            continue
        for package in row.packages:
            seen.setdefault(package, None)
    return list(seen)


#: Packages a contract fragment loads itself, with options ``ts-extra`` must
#: not pre-empt (``glossaries[acronym]``, ``imakeidx[xindy]``), or that only
#: exist for some engines (``fontspec``, ``lua-ul``). ``ts-extra`` skips them.
FRAGMENT_OWNED_PACKAGES: frozenset[str] = frozenset(
    {
        "glossaries",
        "makeidx",
        "imakeidx",
        "fontspec",
        "biblatex",
        "minted",
        "listings",
        "lua-ul",
        "soul",
    }
)

#: Package options ``ts-extra`` applies when a writer names the bare package.
PACKAGE_OPTIONS: Mapping[str, str] = {"ulem": "normalem", "hyphenat": "htt"}


def missing_provides(name: str, defined: Iterable[str]) -> list[str]:
    """Return the ``provides`` entries of contract ``name`` absent from ``defined``."""
    row = fragment_contract(name)
    if row is None:
        return []
    have = set(defined)
    return [entry for entry in row.provides if entry not in have]


def is_contract_fragment(value: Any) -> bool:
    """Whether ``value`` names a row of the contract table."""
    return isinstance(value, str) and value in contract_names()


__all__ = [
    "FRAGMENT_OWNED_PACKAGES",
    "PACKAGE_OPTIONS",
    "FragmentContract",
    "contract_names",
    "fragment_contract",
    "fragment_contracts",
    "implied_packages",
    "is_contract_fragment",
    "missing_provides",
]
