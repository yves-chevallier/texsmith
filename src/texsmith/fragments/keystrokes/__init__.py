from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece


@dataclass(frozen=True)
class KeystrokesConfig:
    uses_keystrokes: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> KeystrokesConfig:
        return cls(uses_keystrokes=_detect_keystrokes(context))

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_keystrokes_enabled"] = self.uses_keystrokes


class KeystrokesFragment(BaseFragment[KeystrokesConfig]):
    name: ClassVar[str] = "ts-keystrokes"
    description: ClassVar[str] = "Keyboard shortcut rendering helpers loaded only when needed."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-keystrokes.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, Any]] = {}
    config_cls: ClassVar[type[KeystrokesConfig]] = KeystrokesConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-keystrokes.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> KeystrokesConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: KeystrokesConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: KeystrokesConfig) -> bool:
        return config.uses_keystrokes


def _detect_keystrokes(context: Mapping[str, Any]) -> bool:
    tokens = ("\\keystroke{", "\\keystrokes{")
    for value in context.values():
        if not isinstance(value, str):
            continue
        if any(token in value for token in tokens):
            return True
    return False


fragment = KeystrokesFragment()

__all__ = ["KeystrokesConfig", "KeystrokesFragment", "fragment"]
