from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from texsmith.core.fragments.activation import required_fragment
from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.fragments.resolution import contract_active
from texsmith.core.templates.manifest import TemplateAttributeSpec
from texsmith.fragments.callouts.words import callout_words_for


@dataclass(frozen=True)
class CalloutsConfig:
    style: str | None
    uses_callouts: bool
    #: ``kind`` → default title of a ``tscallout`` without ``title=``.
    words: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> CalloutsConfig:
        active = contract_active(context, "ts-callouts")
        return cls(
            style=context.get("callout_style"),
            uses_callouts=_detect_callouts(context) if active is None else active,
            words=_callout_words(context),
        )

    def inject_into(self, context: dict[str, Any]) -> None:
        context["ts_callouts_style"] = self.style
        context["ts_callout_words"] = dict(self.words)


def _declared_admonitions(context: Mapping[str, Any]) -> Mapping[str, Any]:
    """``press.declare.admonitions`` of the document, ``{}`` when it declares none."""
    press = context.get("press")
    if not isinstance(press, Mapping):
        return {}
    declare = press.get("declare")
    if not isinstance(declare, Mapping):
        return {}
    admonitions = declare.get("admonitions")
    return admonitions if isinstance(admonitions, Mapping) else {}


def _callout_words(context: Mapping[str, Any]) -> dict[str, str]:
    """Default titles: the capitalised kind, then the labels, in the document's language.

    Four layers, each overruling the one before: the capitalised kind for
    every styled kind, tmark's English label for the standard ones, the
    document language's word for those same ones, and the ``name`` of a kind
    the document declares itself — which is written in the author's language,
    so it is the last word on any kind, declared or standard.
    """
    words: dict[str, str] = {}
    definitions = context.get("callouts_definitions")
    if isinstance(definitions, Mapping):
        for name in definitions:
            key = str(name)
            words[key] = key[:1].upper() + key[1:]
    try:
        import tmark  # type: ignore[import-not-found]

        rows = tmark.registries().get("admonitions", [])
    except Exception:
        rows = []
    for row in rows:
        if isinstance(row, Mapping) and row.get("name") and row.get("label"):
            words[str(row["name"])] = str(row["label"])
    language = context.get("language") or context.get("lang")
    words.update(callout_words_for(language if isinstance(language, str) else None))
    for name, declaration in _declared_admonitions(context).items():
        if not isinstance(declaration, Mapping):
            continue
        title = declaration.get("name")
        if isinstance(title, str) and title.strip():
            words[str(name)] = title.strip()
    return words


class CalloutsFragment(BaseFragment[CalloutsConfig]):
    name: ClassVar[str] = "ts-callouts"
    description: ClassVar[str] = "Reusable callout styles shared by built-in templates."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-callouts.jinja.sty"),
            kind="package",
            variable="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "callout_style": TemplateAttributeSpec(
            default="fancy",
            type="string",
            choices=["fancy", "classic", "minimal"],
            sources=[
                "callouts.style",
                "callout_style",
            ],
            normaliser="callout_style",
        )
    }
    config_cls: ClassVar[type[CalloutsConfig]] = CalloutsConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-callouts.jinja.sty")
    context_defaults: ClassVar[dict[str, Any]] = {"extra_packages": ""}

    def should_render(self, config: CalloutsConfig) -> bool:
        return config.uses_callouts


def _detect_callouts(context: Mapping[str, Any]) -> bool:
    # IR path: the writer named the contract (fragment-contracts.md §2).
    if required_fragment(context, "ts-callouts"):
        return True
    uses_flag = context.get("ts_uses_callouts")
    if isinstance(uses_flag, bool) and uses_flag:
        return True

    for value in context.values():
        if not isinstance(value, str):
            continue
        if "\\begin{callout" in value:
            return True
    return False


fragment = CalloutsFragment()

__all__ = ["CalloutsConfig", "CalloutsFragment", "fragment"]
