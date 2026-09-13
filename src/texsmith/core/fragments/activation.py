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
| ts-extra        | ``extra_packages_from_requires``: what the bodies named, less what the active rows load |
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
    "required_fragment",
]

#: Context key listing the contracts the bodies named.
REQUIRED_FRAGMENTS_KEY = "ts_required_fragments"


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
    """Record the union of the bodies' ``Requires`` on ``state`` (in place, returned).

    The record accumulates: a batch (the CLI in input order, a MkDocs book in
    navigation order) threads one :class:`DocumentState` through every
    document, and the template is wrapped once, at the end — so a contract
    named by the *first* page (``\\tslead`` on page one, ``ts-typesetting``)
    must still be active when the last page names none.
    """
    state.contract_path = True
    state.required_fragments = set(state.required_fragments) | set(requires.fragments)
    # What the bodies named, as they named it. Which of those ``ts-extra`` has
    # to load — and which an active contract already loads — is decided once,
    # by ``extra_packages_from_requires``, where that list is built.
    state.required_packages = list(dict.fromkeys((*state.required_packages, *requires.packages)))
    state.has_index_entries = bool(state.has_index_entries or requires.index)
    state.index_registries = list(dict.fromkeys((*state.index_registries, *requires.index)))
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
    # A key an earlier document of the batch already wrote stays in the glossary.
    known = set(state.acronyms)
    for definition in abbreviations:
        key = state.remember_abbreviation(definition.key, definition.expansion)
        if key and key not in wanted and key not in known:
            # Defined but never written: keep the definition out of the
            # glossary, ``ts-glossary`` declares only the keys that appear.
            state.acronyms.pop(key, None)
            state.acronym_keys.pop(definition.key.strip(), None)
            state.abbreviations.pop(definition.key.strip(), None)
    return state
