from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec


@dataclass(frozen=True)
class CodeConfig:
    options: dict[str, Any]
    uses_code: bool

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> CodeConfig:
        options = context.get("code") or {}
        return cls(options=dict(options), uses_code=_detect_code(context))

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_code_options"] = self.options
        context["ts_code_enabled"] = self.uses_code


class CodeFragment(BaseFragment[CodeConfig]):
    name: ClassVar[str] = "ts-code"
    description: ClassVar[str] = "Configurable code listings used by Markdown code blocks."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-code.jinja.sty"),
            kind="package",
            slot="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "code": TemplateAttributeSpec(
            default={"engine": "pygments", "style": "bw"},
            type="mapping",
            normaliser="code_options",
            sources=[
                "code",
            ],
        )
    }
    config_cls: ClassVar[type[CodeConfig]] = CodeConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-code.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> CodeConfig:
        _ = overrides
        return self.config_cls.from_context(context)

    def inject(
        self,
        config: CodeConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
    ) -> None:
        _ = overrides
        config.inject_into(context)

    def should_render(self, config: CodeConfig) -> bool:
        return config.uses_code


def _detect_code(context: Mapping[str, Any]) -> bool:
    for value in context.values():
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if "\\begin{code" in lowered or "\\begin{minted" in lowered or "\\py{" in lowered:
            return True
    return False


fragment = CodeFragment()

__all__ = ["CodeConfig", "CodeFragment", "fragment"]
