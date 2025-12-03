from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Generic, Literal, TypeVar

from texsmith.core.templates.manifest import TemplateAttributeSpec, TemplateError


FragmentKind = Literal["package", "input", "inline"]


@dataclass(slots=True)
class FragmentPiece:
    """One renderable fragment component."""

    template_path: Path
    kind: FragmentKind = "package"
    slot: str = "extra_packages"
    output_name: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], *, base_dir: Path) -> FragmentPiece:
        """Build a piece from a TOML entry or Python mapping."""
        if not isinstance(payload, Mapping):
            raise TemplateError("Fragment file entries must be mappings.")

        path_value = payload.get("path") or payload.get("template")
        if not path_value or not isinstance(path_value, str):
            raise TemplateError("Fragment file entries require a 'path' or 'template' string.")

        candidate_path = Path(path_value)
        resolved_path = (
            candidate_path
            if candidate_path.is_absolute()
            else (base_dir / candidate_path).resolve()
        )

        if not resolved_path.exists():
            raise TemplateError(f"Fragment file is missing: {resolved_path}")

        kind_raw = payload.get("type", "package")
        if kind_raw not in ("package", "input", "inline"):
            raise TemplateError(
                f"Unknown fragment file type '{kind_raw}'. Expected one of: package, input, inline."
            )

        slot = str(payload.get("slot", "extra_packages"))
        output_name = payload.get("output") if isinstance(payload.get("output"), str) else None

        return cls(
            template_path=resolved_path,
            kind=kind_raw,  # type: ignore[arg-type]
            slot=slot,
            output_name=output_name,
        )

    def _ensure_suffix(self, name: str) -> str:
        suffix = ".sty" if self.kind == "package" else ".tex"
        return name if name.endswith(suffix) else f"{name}{suffix}"

    def output_filename(self, fragment_name: str) -> str | None:
        """Return the rendered filename, if applicable."""
        if self.kind == "inline":
            return None
        base = self.output_name or fragment_name
        normalised = Path(base).name
        return self._ensure_suffix(normalised)


C = TypeVar("C")


class BaseFragment(ABC, Generic[C]):
    """Base contract for object-oriented fragments."""

    name: ClassVar[str]
    description: ClassVar[str]
    pieces: ClassVar[list[FragmentPiece]]
    attributes: ClassVar[dict[str, TemplateAttributeSpec]]
    config_cls: ClassVar[type[C]]
    context_defaults: ClassVar[dict[str, Any]] = {}
    partials: ClassVar[Mapping[str, Path | str] | Sequence[Path | str]] = ()
    required_partials: ClassVar[Sequence[str]] = ()
    source: ClassVar[Path | None] = None

    @abstractmethod
    def build_config(
        self, context: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> C:
        """Return a normalized config instance from the provided context."""
        raise NotImplementedError

    @abstractmethod
    def inject(
        self, config: C, context: dict[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> None:
        """Inject Jinja/templating context variables derived from the config."""
        raise NotImplementedError

    @abstractmethod
    def should_render(self, config: C) -> bool:
        """Return whether this fragment should render given the config."""
        raise NotImplementedError

    def render_context(
        self, context: dict[str, Any], overrides: Mapping[str, Any] | None = None
    ) -> C:
        """Build config and inject into a mutable context; return the config."""
        config = self.build_config(context, overrides=overrides)
        self.inject(config, context, overrides=overrides)
        return config


__all__ = ["BaseFragment", "FragmentKind", "FragmentPiece"]
