from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from texsmith.core.coerce import coerce_bool
from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec, TemplateError
from texsmith.diagnostics import DiagnosticEmitter


_DEFAULT_MARGIN = "0pt"
_DEFAULT_FOLD_SIZE = "10mm"


#: The frame's own mode words → whether the mode draws the dogear. One table:
#: it answers ``press.frame: dogear``, ``press.frame: {mode: fold}`` and a
#: mode word given where a boolean is expected (``{dogear: border}``).
_MODE_WORDS = {"dogear": True, "fold": True, "border": False}


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, str):
        mode = _MODE_WORDS.get(value.strip().lower())
        if mode is not None:
            return mode
    resolved = coerce_bool(value)
    return default if resolved is None else resolved


class FrameConfig(BaseModel):
    """Validated representation of the press.frame options."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = False
    dogear: bool = False
    margin: str | None = None
    fold_size: str | None = Field(default=None, alias="fold-size")

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload(cls, data: Any) -> Any:
        if isinstance(data, FrameConfig):
            return data.model_dump()
        if data is None:
            return {"enabled": False}
        if isinstance(data, Mapping):
            payload = dict(data)
            enabled = _coerce_bool(payload.get("enabled"), default=True)
            mode = payload.get("mode")
            dogear_value = payload.get("dogear")
            if isinstance(mode, str):
                resolved = _MODE_WORDS.get(mode.strip().lower())
                if resolved is not None:
                    dogear_value = resolved
                    enabled = True
            dogear_flag = _coerce_bool(dogear_value, default=True)
            fold_size = payload.get("fold-size") or payload.get("fold_size") or payload.get("fold")
            margin = payload.get("margin")
            if not enabled:
                return {"enabled": False}
            return {
                "enabled": True,
                "dogear": dogear_flag,
                "margin": margin,
                "fold_size": fold_size,
            }
        if isinstance(data, (bool, int, float)):
            flag = bool(data)
            return {"enabled": flag, "dogear": flag}
        if isinstance(data, str):
            token = data.strip().lower()
            if not token or token in {"false", "off", "no", "0", "none"}:
                return {"enabled": False}
            mode = _MODE_WORDS.get(token)
            if mode is not None:
                return {"enabled": True, "dogear": mode}
            if coerce_bool(token):
                return {"enabled": True, "dogear": True}
            raise TemplateError(
                "press.frame accepts false, true, or one of "
                + ", ".join(f"'{word}'" for word in _MODE_WORDS)
                + "."
            )
        raise TemplateError("press.frame must be a boolean, string, or mapping.")

    @field_validator("margin", "fold_size", mode="before")
    @classmethod
    def _normalise_length(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return f"{value}mm"
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return str(value)

    @model_validator(mode="after")
    def _disable_when_empty(self) -> FrameConfig:
        if not self.enabled:
            object.__setattr__(self, "dogear", False)
        return self

    def effective_margin(self) -> str:
        return self.margin or _DEFAULT_MARGIN

    def effective_fold_size(self) -> str:
        return self.fold_size or _DEFAULT_FOLD_SIZE


class FrameFragment(BaseFragment[FrameConfig]):
    """Optional page frame with an optional folded corner."""

    name: ClassVar[str] = "ts-frame"
    description: ClassVar[str] = "Draw a page frame (with optional dogear) on each page."
    pieces: ClassVar[list[FragmentPiece]] = [
        FragmentPiece(
            template_path=Path(__file__).with_name("ts-frame.tex.jinja"),
            kind="inline",
            variable="extra_packages",
        )
    ]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]] = {
        "frame_spec": TemplateAttributeSpec(
            default=None,
            sources=["frame"],
        )
    }
    config_cls: ClassVar[type[FrameConfig]] = FrameConfig
    source: ClassVar[Path] = Path(__file__).with_name("ts-frame.tex.jinja")
    context_defaults: ClassVar[dict[str, Any]] = {
        "ts_frame_enabled": False,
        "ts_frame_dogear": False,
        "ts_frame_margin": _DEFAULT_MARGIN,
        "ts_frame_fold_size": _DEFAULT_FOLD_SIZE,
    }

    def build_config(
        self,
        context: Mapping[str, Any],
        overrides: Mapping[str, Any] | None = None,
        *,
        emitter: DiagnosticEmitter | None = None,
    ) -> FrameConfig:
        _ = overrides
        _ = emitter
        raw_value = context.get("frame_spec") or context.get("frame")
        try:
            return self.config_cls.model_validate(raw_value)
        except ValidationError as exc:
            raise TemplateError(f"Invalid frame settings: {exc}") from exc

    def inject(
        self,
        config: FrameConfig,
        context: dict[str, Any],
        overrides: Mapping[str, Any] | None = None,
        *,
        emitter: DiagnosticEmitter | None = None,
    ) -> None:
        _ = overrides
        _ = emitter
        context["ts_frame_enabled"] = config.enabled
        context["ts_frame_dogear"] = bool(config.enabled and config.dogear)
        context["ts_frame_margin"] = config.effective_margin()
        context["ts_frame_fold_size"] = config.effective_fold_size()

    def should_render(self, config: FrameConfig) -> bool:
        return bool(config.enabled)


fragment = FrameFragment()

__all__ = ["FrameConfig", "FrameFragment", "fragment"]
