from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.activation import required_fragment
from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.fragments.resolution import contract_active


#: ``KEY_LABELS`` of ``tmark_ir::registry`` (the label a key name renders
#: as); read from ``tmark.registries()`` when the wheel is importable. The
#: writer already applies the table, so the fragment's copy only serves a
#: writer that emits raw key names.
_FALLBACK_KEY_LABELS: dict[str, str] = {
    "control": "Ctrl",
    "ctrl": "Ctrl",
    "alt": "Alt",
    "delete": "Del",
    "del": "Del",
    "enter": "⏎ Enter",
    "return": "⏎ Enter",
    "shift": "⇧ Shift",
    "slash": "/",
    "comma": ",",
    "period": ".",
    "backslash": "\\",
    "double-quote": '"',
    "backspace": "⌫ Delete",
    "command": "⌘",
    "cmd": "⌘",
    "tab": "Tab",
    "esc": "Esc",
    "escape": "Esc",
    "insert": "Ins",
    "home": "Home",
    "end": "End",
    "page-up": "PgUp",
    "page-down": "PgDn",
    "space": "Space",
}


def key_labels() -> dict[str, str]:
    """Return the key-label table, from ``tmark`` when importable."""
    try:
        import tmark  # type: ignore[import-not-found]

        rows = tmark.registries().get("key_labels", [])
    except Exception:
        rows = []
    table: dict[str, str] = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("name") and row.get("label") is not None:
            table[str(row["name"])] = str(row["label"])
    return table or dict(_FALLBACK_KEY_LABELS)


_LATEX_KEY_LABELS: dict[str, str] = {
    "\\": "\\textbackslash{}",
    "↑": "\\(\\uparrow\\)",
    "↓": "\\(\\downarrow\\)",
    "←": "\\(\\leftarrow\\)",
    "→": "\\(\\rightarrow\\)",
    ",": "{,}",
    '"': "\\textquotedbl{}",
}


def _ascii_tex(text: str) -> str:
    """Spell non-ASCII characters as ``^^^^xxxx`` so the table stays ASCII.

    The engine-selection heuristics scan the context for glyphs the current
    engine cannot typeset; the table must not trigger them on its own (the
    writer only emits the labels a document uses). XeTeX and LuaTeX read
    ``^^^^xxxx``; pdfTeX cannot typeset those glyphs anyway.
    """
    out: list[str] = []
    for char in text:
        code = ord(char)
        if code < 128:
            out.append(char)
        elif code <= 0xFFFF:
            out.append(f"^^^^{code:04x}")
        else:
            out.append(f"^^^^^^{code:06x}")
    return "".join(out)


def latex_key_labels() -> list[tuple[str, str]]:
    """The label table with the labels LaTeX can typeset, name-sorted."""
    return sorted(
        (name, _ascii_tex(_LATEX_KEY_LABELS.get(label, label)))
        for name, label in key_labels().items()
        if name.replace("-", "").isalnum()
    )


@dataclass(frozen=True)
class KeystrokesConfig:
    uses_keystrokes: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> KeystrokesConfig:
        active = contract_active(context, "ts-keystrokes")
        return cls(uses_keystrokes=_detect_keystrokes(context) if active is None else active)

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_keystrokes_enabled"] = self.uses_keystrokes
        context["ts_key_labels"] = latex_key_labels()


class KeystrokesFragment(BaseFragment[KeystrokesConfig]):
    name: ClassVar[str] = "ts-keystrokes"
    description: ClassVar[str] = "Keyboard shortcut rendering helpers loaded only when needed."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-keystrokes.jinja.sty"),
            kind="package",
            variable="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[KeystrokesConfig]] = KeystrokesConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-keystrokes.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def should_render(self, config: KeystrokesConfig) -> bool:
        return config.uses_keystrokes


def _detect_keystrokes(context: Mapping[str, Any]) -> bool:
    # IR path: the writer named the contract (fragment-contracts.md §2).
    if required_fragment(context, "ts-keystrokes"):
        return True
    tokens = ("\\keystroke{", "\\keystrokes{")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


fragment = KeystrokesFragment()

__all__ = ["KeystrokesConfig", "KeystrokesFragment", "fragment"]
