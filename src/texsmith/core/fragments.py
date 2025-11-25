"""Pluggable fragment helpers (templated .sty packages)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any, Literal


try:  # Python >=3.11
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from texsmith.core.templates.base import _build_environment
from texsmith.core.templates.manifest import TemplateError


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


@dataclass(slots=True)
class FragmentDefinition:
    """Resolved fragment template ready to render."""

    name: str
    pieces: list[FragmentPiece]
    description: str | None = None
    source: Path | None = None
    context_defaults: dict[str, Any] = field(default_factory=dict)
    context_injector: Callable[[dict[str, Any], Mapping[str, Any] | None], None] | None = None
    should_render: Callable[[Mapping[str, Any]], bool] | None = None

    @classmethod
    def from_manifest(cls, manifest_path: Path) -> FragmentDefinition:
        """Load a fragment definition from a ``fragment.toml`` file."""
        try:
            payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError as exc:  # pragma: no cover - IO edge cases
            raise TemplateError(f"Failed to read fragment manifest {manifest_path}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise TemplateError(f"Invalid fragment manifest {manifest_path}: {exc}") from exc

        base_dir = manifest_path.parent

        entrypoint = payload.get("entrypoint")
        if isinstance(entrypoint, str):
            return _load_entrypoint(entrypoint, fallback_dir=base_dir)

        name = payload.get("name") if isinstance(payload.get("name"), str) else None
        description = (
            payload.get("description") if isinstance(payload.get("description"), str) else None
        )
        files = payload.get("files") or []
        if not name:
            name = base_dir.name
        if not isinstance(files, list) or not files:
            raise TemplateError(
                f"Fragment manifest {manifest_path} must declare at least one file."
            )

        pieces = [FragmentPiece.from_mapping(entry, base_dir=base_dir) for entry in files]
        return cls(
            name=name,
            pieces=pieces,
            description=description,
            source=manifest_path,
            context_defaults={},
        )

    @classmethod
    def from_path(cls, path: Path, *, name: str | None = None) -> FragmentDefinition:
        """Fallback builder for legacy one-file fragments."""
        resolved = path.resolve()
        if not resolved.exists():
            raise TemplateError(f"Fragment path does not exist: {resolved}")

        fragment_name = name or _package_name(resolved.name)
        piece = FragmentPiece(template_path=resolved, kind="package", slot="extra_packages")
        return cls(name=fragment_name, pieces=[piece], source=resolved, context_defaults={})


def _package_name(identifier: str) -> str:
    candidate = Path(identifier)
    name = candidate.name
    for suffix in (".jinja.sty", ".jinja.tex", ".sty", ".tex"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return Path(name).stem


def _load_entrypoint(entrypoint: str, *, fallback_dir: Path) -> FragmentDefinition:
    """Load a fragment definition from a Python callable."""
    module_name, _, attr = entrypoint.partition(":")
    if not module_name or not attr:
        raise TemplateError("Fragment entrypoint must be in the form 'module:attribute'.")

    module = importlib.import_module(module_name)
    factory: Callable[..., Any] = getattr(module, attr)
    definition = factory()

    if isinstance(definition, FragmentDefinition):
        return definition

    if isinstance(definition, Mapping):
        files = definition.get("files") or []
        name = definition.get("name") or fallback_dir.name
        description = definition.get("description")
        pieces = [FragmentPiece.from_mapping(entry, base_dir=fallback_dir) for entry in files]
        return FragmentDefinition(
            name=name,
            pieces=pieces,
            description=description if isinstance(description, str) else None,
            source=fallback_dir,
        )

    raise TemplateError(
        f"Fragment entrypoint '{entrypoint}' must return a FragmentDefinition or mapping."
    )


class FragmentRegistry:
    """Central registry resolving fragment templates."""

    def __init__(self, *, root: Path, default_order: Sequence[str]) -> None:
        self._root = root
        self._default_order = list(default_order)
        self._fragments: dict[str, FragmentDefinition] = {}
        self._discover_builtins()

    @property
    def default_fragment_names(self) -> list[str]:
        return [name for name in self._default_order if name in self._fragments]

    def register_fragment(
        self, fragment: FragmentDefinition | Path | str, *, name: str | None = None
    ) -> None:
        """Register a custom fragment definition (path or definition instance)."""
        if isinstance(fragment, FragmentDefinition):
            definition = fragment
        else:
            definition = FragmentDefinition.from_path(Path(fragment), name=name)
        self._fragments[definition.name] = definition

    def resolve(self, name: str, *, source_dir: Path | None = None) -> FragmentDefinition:
        if name in self._fragments:
            return self._fragments[name]

        candidate = Path(name)
        if not candidate.is_absolute() and source_dir is not None:
            candidate = (source_dir / candidate).resolve()
        if candidate.is_dir():
            manifest_path = candidate / "fragment.toml"
            definition = FragmentDefinition.from_manifest(manifest_path)
        elif candidate.is_file() and candidate.name == "fragment.toml":
            definition = FragmentDefinition.from_manifest(candidate)
        elif candidate.exists():
            definition = FragmentDefinition.from_path(candidate, name=name)
        else:
            raise TemplateError(f"Fragment '{name}' could not be resolved.")

        self._fragments.setdefault(definition.name, definition)
        return definition

    def _discover_builtins(self) -> None:
        if not self._root.exists():
            return

        for manifest in sorted(self._root.rglob("fragment.toml")):
            definition = FragmentDefinition.from_manifest(manifest)
            self._fragments.setdefault(definition.name, definition)


@dataclass(slots=True)
class FragmentRenderResult:
    """Rendered artefacts for selected fragments."""

    packages: list[str]
    variable_injections: dict[str, list[str]]
    providers: dict[str, list[str]]
    written: list[Path]


BUILTIN_FRAGMENT_ORDER = [
    "ts-geometry",
    "ts-fonts",
    "ts-extra",
    "ts-callouts",
    "ts-code",
    "ts-glossary",
    "ts-index",
    "ts-todolist",
]

FRAGMENT_ROOT = Path(__file__).resolve().parent.parent / "builtin_fragments"
FRAGMENT_REGISTRY = FragmentRegistry(root=FRAGMENT_ROOT, default_order=BUILTIN_FRAGMENT_ORDER)


def register_fragment(
    fragment: FragmentDefinition | Path | str,
    path: Path | None = None,
    *,
    name: str | None = None,
) -> None:
    """Register a custom fragment path (mainly for extensions/tests)."""
    if path is not None:
        derived_name = name or (fragment if isinstance(fragment, str) else None)
        definition = FragmentDefinition.from_path(Path(path), name=derived_name)
        FRAGMENT_REGISTRY.register_fragment(definition)
        return
    FRAGMENT_REGISTRY.register_fragment(fragment, name=name)


def render_fragments(
    names: Iterable[str],
    *,
    context: Mapping[str, Any],
    output_dir: Path,
    source_dir: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    declared_slots: set[str] | None = None,
    declared_variables: set[str] | None = None,
    template_name: str | None = None,
) -> FragmentRenderResult:
    """
    Render the selected fragments into ``output_dir`` and return the injected variables.
    """
    rendered_packages: list[str] = []
    written: list[Path] = []
    variable_injections: dict[str, list[str]] = {}
    providers: dict[str, list[str]] = {}

    if not isinstance(context, dict):
        raise TemplateError("Fragment rendering requires a mutable context dictionary.")

    for name in names:
        fragment = FRAGMENT_REGISTRY.resolve(name, source_dir=source_dir)
        if declared_slots is not None:
            for piece in fragment.pieces:
                target_slot = piece.slot
                if target_slot in declared_slots:
                    raise TemplateError(
                        f"Fragments cannot target slot '{target_slot}' in template "
                        f"'{template_name or 'unknown'}'."
                    )
                if declared_variables is not None and target_slot not in declared_variables:
                    raise TemplateError(
                        f"Template '{template_name or 'unknown'}' doesn't declare variable "
                        f"'{target_slot}' required by fragment '{fragment.name}'."
                    )

        for key, value in fragment.context_defaults.items():
            context.setdefault(key, value)

        if fragment.context_injector is not None:
            fragment.context_injector(context, overrides)

        if fragment.should_render is not None:
            try:
                if not fragment.should_render(context):
                    continue
            except Exception:
                pass

        for piece in fragment.pieces:
            env = _build_environment(piece.template_path.parent)
            template = env.get_template(piece.template_path.name)
            payload = template.render(**context)

            target_slot = piece.slot
            if piece.kind == "inline":
                injection = payload.strip()
                if injection:
                    variable_injections.setdefault(target_slot, []).append(injection)
                    providers.setdefault(target_slot, []).append(fragment.name)
                continue

            output_name = piece.output_filename(fragment.name)
            if output_name is None:
                continue

            output_path = output_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            written.append(output_path)

            if piece.kind == "package":
                rendered_packages.append(Path(output_name).stem)
                injection = f"\\usepackage{{{Path(output_name).stem}}}"
            else:
                injection = f"\\input{{{Path(output_name).name}}}"

            variable_injections.setdefault(target_slot, []).append(injection)
            providers.setdefault(target_slot, []).append(fragment.name)

    return FragmentRenderResult(
        packages=rendered_packages,
        variable_injections=variable_injections,
        providers=providers,
        written=written,
    )


__all__ = [
    "FRAGMENT_REGISTRY",
    "FragmentDefinition",
    "FragmentPiece",
    "FragmentRegistry",
    "FragmentRenderResult",
    "register_fragment",
    "render_fragments",
]
