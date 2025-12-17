from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from texsmith.core.fragments.base import BaseFragment, FragmentPiece
from texsmith.core.templates.manifest import TemplateAttributeSpec, TemplateError


_DEFAULT_MARGIN = "0pt"
_DEFAULT_FOLD_SIZE = "10mm"


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if not token:
            return default
        if token in {"true", "yes", "on", "1", "dogear"}:
            return True
        if token in {"false", "no", "off", "0", "border"}:
            return False
    return default


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
                token = mode.strip().lower()
                if token == "border":
                    dogear_value = False
                    enabled = True
                elif token in {"dogear", "fold"}:
                    dogear_value = True
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
            if token == "border":
                return {"enabled": True, "dogear": False}
            if token in {"dogear", "true", "yes", "on", "1"}:
                return {"enabled": True, "dogear": True}
            raise TemplateError("press.frame accepts false, true, 'border', or 'dogear'.")
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
            slot="extra_packages",
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
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> FrameConfig:
        _ = overrides
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
    ) -> None:
        _ = overrides
        context["ts_frame_enabled"] = config.enabled
        context["ts_frame_dogear"] = bool(config.enabled and config.dogear)
        context["ts_frame_margin"] = config.effective_margin()
        context["ts_frame_fold_size"] = config.effective_fold_size()

    def should_render(self, config: FrameConfig) -> bool:
        return bool(config.enabled)


fragment = FrameFragment()

__all__ = ["FrameConfig", "FrameFragment", "fragment"]
