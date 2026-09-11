"""Fragment activation from ``Requires`` (``fragment-contracts.md`` §2, task 3.5).

On the IR path the writer names what a body needs; this module turns the
union of the bodies' ``Requires`` into the :class:`DocumentState` flags the
template wrapper and the fragments read, replacing the string sniffers of
the HTML path for that path only:

| Fragment        | Active when                                                   |
| --------------- | ------------------------------------------------------------- |
| any row         | its name is in ``Requires.fragments`` (``ts_required_fragments``) |
| ts-index        | ``Requires.index`` non-empty; registries in ``index_registries`` |
| ts-bibliography | ``Requires.bibliography``; cited keys are ``citations``        |
| ts-glossary     | ``ts-glossary`` required, entries from ``Document.abbreviations`` |
| ts-code         | as row one; ``requires_shell_escape`` from ``Requires.shell_escape`` |
| ts-extra        | packages = ``Requires.packages`` minus the packages the active rows imply |
| ts-fonts, ts-geometry, ts-frame | unchanged (configuration, not contracts)      |

A ``press.fragments`` entry not in the table renders unconditionally, as today.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from texsmith.core.context import DocumentState


if TYPE_CHECKING:  # pragma: no cover - typing only
    from texsmith.core.conversion.bodies import Requires
    from texsmith.ir import model


__all__ = [
    "apply_requires",
    "fragment_table",
    "implied_packages",
    "required_fragment",
]

#: Context key listing the contracts the bodies named.
REQUIRED_FRAGMENTS_KEY = "ts_required_fragments"
#: Context key listing the packages ``ts-extra`` must load for the bodies.
REQUIRED_PACKAGES_KEY = "ts_required_packages"


@lru_cache(maxsize=1)
def fragment_table() -> dict[str, dict[str, Any]]:
    """The ``FRAGMENTS`` rows of tmark keyed by contract name (empty without the wheel)."""
    try:
        import tmark
    except ImportError:  # pragma: no cover - the wheel is a dependency
        return {}
    try:
        rows = tmark.fragments()
    except Exception:  # pragma: no cover - defensive
        return {}
    return {str(row["name"]): dict(row) for row in rows if isinstance(row, Mapping)}


def implied_packages(fragments: Iterable[str]) -> set[str]:
    """The LaTeX packages the named contracts load themselves."""
    table = fragment_table()
    packages: set[str] = set()
    for name in fragments:
        row = table.get(name)
        if row is None:
            continue
        packages.update(str(item) for item in row.get("packages") or ())
    return packages


def required_fragment(context: Mapping[str, Any], name: str) -> bool:
    """Whether a body named the contract ``name`` (``ts_required_fragments`` in the context)."""
    required = context.get(REQUIRED_FRAGMENTS_KEY)
    if isinstance(required, str):
        return required == name
    if isinstance(required, Iterable):
        return name in set(required)
    return False


def apply_requires(
    state: DocumentState,
    requires: Requires,
    *,
    abbreviations: Iterable[model.AbbrDef] = (),
    template_shell_escape: bool = False,
) -> DocumentState:
    """Record the union of the bodies' ``Requires`` on ``state`` (in place, returned)."""
    state.contract_path = True
    state.required_fragments = set(requires.fragments)
    implied = implied_packages(requires.fragments)
    state.required_packages = [pkg for pkg in requires.packages if pkg not in implied]
    state.has_index_entries = bool(requires.index)
    state.index_registries = list(requires.index)
    state.requires_shell_escape = bool(
        state.requires_shell_escape or requires.shell_escape or template_shell_escape
    )
    state.callouts_used = "ts-callouts" in state.required_fragments
    for key in requires.citations:
        state.record_citation(key)
    # ``\tsacr{key}`` uses the LaTeX key rule (``slugify(term, "", lowercase=False)``
    # with collision suffixes), the same ``remember_abbreviation`` applies, so
    # registering the definitions in document order reproduces the keys.
    wanted = set(requires.acronyms)
    for definition in abbreviations:
        key = state.remember_abbreviation(definition.key, definition.expansion)
        if key and key not in wanted:
            # Defined but never written: keep the definition out of the
            # glossary, ``ts-glossary`` declares only the keys that appear.
            state.acronyms.pop(key, None)
            state.acronym_keys.pop(definition.key.strip(), None)
            state.abbreviations.pop(definition.key.strip(), None)
    return state
