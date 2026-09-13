"""Pluggable fragment helpers (templated .sty packages)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import warnings


try:  # Python >=3.11
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from texsmith.core.fragments.base import BaseFragment, FragmentKind, FragmentPiece
from texsmith.core.templates.base import _build_environment
from texsmith.core.templates.manifest import (
    TemplateAttributeResolver,
    TemplateAttributeSpec,
    TemplateError,
    _import_object,
)


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
    attributes: dict[str, TemplateAttributeSpec] = field(default_factory=dict)
    _attribute_resolver: TemplateAttributeResolver | None = field(
        init=False, repr=False, default=None
    )

    def __post_init__(self) -> None:
        if self.attributes:
            normalised: dict[str, TemplateAttributeSpec] = {}
            for name, spec in self.attributes.items():
                if isinstance(spec, TemplateAttributeSpec):
                    candidate = spec
                elif isinstance(spec, Mapping):
                    candidate = TemplateAttributeSpec.model_validate(spec)
                else:
                    candidate = TemplateAttributeSpec.model_validate({"default": spec})
                candidate.name = name
                if candidate.owner is None:
                    candidate.owner = self.name
                normalised[name] = candidate

            object.__setattr__(self, "attributes", normalised)
            object.__setattr__(self, "_attribute_resolver", TemplateAttributeResolver(normalised))

    def attribute_defaults(self) -> dict[str, Any]:
        """Return defaults for fragment-managed attributes."""
        if self._attribute_resolver is None:
            return {}
        return self._attribute_resolver.defaults()

    def resolve_attributes(self, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return resolved fragment attributes merged with overrides."""
        if self._attribute_resolver is None:
            return {}
        return self._attribute_resolver.merge(overrides)

    @classmethod
    def from_manifest(cls, manifest_path: Path) -> BaseFragment[Any] | FragmentDefinition:
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
            return _load_entrypoint(entrypoint)

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
        attributes: dict[str, TemplateAttributeSpec] = {}
        declared_attrs = payload.get("attributes")
        if isinstance(declared_attrs, Mapping):
            for key, value in declared_attrs.items():
                attributes[key] = (
                    value
                    if isinstance(value, TemplateAttributeSpec)
                    else TemplateAttributeSpec.model_validate(value)
                    if isinstance(value, Mapping)
                    else TemplateAttributeSpec.model_validate({"default": value})
                )
        return cls(
            name=name,
            pieces=pieces,
            description=description,
            source=manifest_path,
            context_defaults={},
            attributes=attributes,
        )

    @classmethod
    def from_path(cls, path: Path, *, name: str | None = None) -> FragmentDefinition:
        """Build a fragment definition from a single template path."""
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


def _load_entrypoint(entrypoint: str) -> BaseFragment[Any] | FragmentDefinition:
    """Load a fragment definition from a Python callable."""
    target = _import_object(entrypoint)
    candidate = target() if callable(target) else target

    if isinstance(candidate, (BaseFragment, FragmentDefinition)):
        return candidate

    raise TemplateError(
        f"Fragment entrypoint '{entrypoint}' must return a BaseFragment or FragmentDefinition."
    )


def _normalise_fragment_attributes(
    fragment: BaseFragment[Any],
) -> tuple[dict[str, TemplateAttributeSpec], TemplateAttributeResolver | None]:
    raw = getattr(fragment, "attributes", {}) or {}
    if not raw:
        return {}, None

    normalised: dict[str, TemplateAttributeSpec] = {}
    for name, spec in raw.items():
        if isinstance(spec, TemplateAttributeSpec):
            candidate = spec
        elif isinstance(spec, Mapping):
            candidate = TemplateAttributeSpec.model_validate(spec)
        else:
            candidate = TemplateAttributeSpec.model_validate({"default": spec})
        candidate.name = name
        if candidate.owner is None:
            candidate.owner = fragment.name
        normalised[name] = candidate

    resolver = TemplateAttributeResolver(normalised)
    return normalised, resolver


class FragmentRegistry:
    """Central registry resolving fragment templates."""

    def __init__(self, *, root: Path, default_order: Sequence[str]) -> None:
        self._root = root
        self._default_order = list(default_order)
        self._fragments: dict[str, BaseFragment[Any] | FragmentDefinition] = {}
        self._attributes: dict[str, dict[str, TemplateAttributeSpec]] = {}
        self._attribute_resolvers: dict[str, TemplateAttributeResolver] = {}
        self._discover_builtins()
        self._discover_entry_points()

    @property
    def default_fragment_names(self) -> list[str]:
        return [name for name in self._default_order if name in self._fragments]

    def attributes_for(self, name: str) -> dict[str, TemplateAttributeSpec]:
        return self._attributes.get(name, {})

    def attribute_resolver_for(self, name: str) -> TemplateAttributeResolver | None:
        return self._attribute_resolvers.get(name)

    def register_fragment(
        self,
        fragment: BaseFragment[Any] | FragmentDefinition | Path | str,
        *,
        name: str | None = None,
    ) -> None:
        """Register a custom fragment definition (path or definition instance)."""
        if isinstance(fragment, (BaseFragment, FragmentDefinition)):
            self._register_fragment_object(fragment)
            return

        definition = FragmentDefinition.from_path(Path(fragment), name=name)
        self._register_fragment_object(definition)

    def resolve(
        self, name: str, *, source_dir: Path | None = None
    ) -> BaseFragment[Any] | FragmentDefinition:
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

        self._register_fragment_object(definition)
        return self._fragments[definition.name]

    def _discover_builtins(self) -> None:
        if not self._root.exists():
            return

        for manifest in sorted(self._root.rglob("fragment.toml")):
            definition = FragmentDefinition.from_manifest(manifest)
            self._register_fragment_object(definition)

    def _discover_entry_points(self) -> None:
        """Discover fragments contributed by installed Python packages.

        A package opts in by declaring an ``texsmith.fragments`` entry point
        whose value resolves to either a :class:`Path` (a fragment directory
        or a ``fragment.toml`` file) or a :class:`FragmentDefinition`. This
        lets fragments live in their own pip-installable distributions
        without being copied into the texsmith tree or referenced by path.
        """
        from importlib.metadata import entry_points

        try:
            discovered = entry_points(group="texsmith.fragments")
        except TypeError:  # pragma: no cover - pre-3.10 compat path
            discovered = entry_points().get("texsmith.fragments", [])  # type: ignore[attr-defined]

        for entry in discovered:
            try:
                target = entry.load()
            except Exception as exc:  # pragma: no cover - defensive
                warnings.warn(
                    f"Failed to load texsmith fragment entry point '{entry.name}': {exc}",
                    stacklevel=2,
                )
                continue

            if callable(target) and not isinstance(
                target, (Path, FragmentDefinition, BaseFragment)
            ):
                target = target()

            if isinstance(target, (BaseFragment, FragmentDefinition)):
                self._register_fragment_object(target)
                continue

            candidate = Path(target)
            if candidate.is_dir():
                manifest_path = candidate / "fragment.toml"
                if not manifest_path.is_file():
                    warnings.warn(
                        f"texsmith fragment entry point '{entry.name}' points to "
                        f"'{candidate}' but it has no fragment.toml.",
                        stacklevel=2,
                    )
                    continue
                definition = FragmentDefinition.from_manifest(manifest_path)
            elif candidate.is_file() and candidate.name == "fragment.toml":
                definition = FragmentDefinition.from_manifest(candidate)
            else:
                warnings.warn(
                    f"texsmith fragment entry point '{entry.name}' resolved to "
                    f"'{candidate}', which is neither a fragment directory nor a "
                    "fragment.toml file.",
                    stacklevel=2,
                )
                continue

            self._register_fragment_object(definition)

    def _register_fragment_object(self, fragment: BaseFragment[Any] | FragmentDefinition) -> None:
        if isinstance(fragment, BaseFragment):
            self._fragments[fragment.name] = fragment
            normalised_attributes, resolver = _normalise_fragment_attributes(fragment)
            if normalised_attributes:
                self._attributes[fragment.name] = normalised_attributes
            if resolver:
                self._attribute_resolvers[fragment.name] = resolver
            return

        self._fragments.setdefault(fragment.name, fragment)


@dataclass(slots=True)
class FragmentRenderResult:
    """Rendered artefacts for selected fragments."""

    packages: list[str]
    variable_injections: dict[str, list[str]]
    providers: dict[str, list[str]]
    written: list[Path]


BUILTIN_FRAGMENT_ORDER = [
    "ts-geometry",
    "ts-typesetting",
    "ts-frame",
    "ts-fonts",
    "ts-extra",
    "ts-keystrokes",
    "ts-callouts",
    "ts-code",
    "ts-glossary",
    "ts-index",
    "ts-bibliography",
    "ts-todolist",
    "ts-critic",
]

FRAGMENT_ROOT = Path(__file__).resolve().parent.parent.parent / "fragments"
FRAGMENT_REGISTRY = FragmentRegistry(root=FRAGMENT_ROOT, default_order=BUILTIN_FRAGMENT_ORDER)


def register_fragment(
    fragment: BaseFragment[Any] | FragmentDefinition | Path | str,
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


def _resolve_fragments(
    names: Iterable[str], *, source_dir: Path | None = None
) -> list[BaseFragment[Any] | FragmentDefinition]:
    return [FRAGMENT_REGISTRY.resolve(name, source_dir=source_dir) for name in names]


def collect_fragment_attribute_defaults(
    names: Iterable[str], *, source_dir: Path | None = None
) -> dict[str, Any]:
    """Return default attributes declared by the provided fragments."""
    defaults: dict[str, Any] = {}
    for fragment in _resolve_fragments(names, source_dir=source_dir):
        if isinstance(fragment, FragmentDefinition):
            for key, value in fragment.attribute_defaults().items():
                defaults.setdefault(key, value)
            continue

        attributes = FRAGMENT_REGISTRY.attributes_for(fragment.name)
        resolver = FRAGMENT_REGISTRY.attribute_resolver_for(fragment.name)
        if attributes and resolver:
            for key, value in resolver.defaults().items():
                defaults.setdefault(key, value)
    return defaults


def inject_fragment_attributes(
    names: Iterable[str],
    *,
    context: dict[str, Any],
    overrides: Mapping[str, Any] | None = None,
    source_dir: Path | None = None,
    declared_attribute_owners: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Populate ``context`` with fragment-owned attributes."""
    if not isinstance(context, dict):
        raise TemplateError("Fragment attribute injection requires a mutable context dictionary.")

    owners: dict[str, str] = dict(declared_attribute_owners or {})
    injected: dict[str, Any] = {}
    for fragment in _resolve_fragments(names, source_dir=source_dir):
        if isinstance(fragment, FragmentDefinition):
            resolved = fragment.resolve_attributes(overrides)
            for attr_name in fragment.attributes:
                owner = fragment.attributes[attr_name].owner or fragment.name
                existing = owners.get(attr_name)
                if existing and existing != owner:
                    raise TemplateError(
                        f"Attribute '{attr_name}' already owned by '{existing}', conflict with '{owner}'."
                    )
                owners[attr_name] = owner
            for key, value in resolved.items():
                context[key] = value
                injected[key] = value
            continue

        attributes = FRAGMENT_REGISTRY.attributes_for(fragment.name)
        resolver = FRAGMENT_REGISTRY.attribute_resolver_for(fragment.name)
        resolved = resolver.merge(overrides) if resolver else {}
        for attr_name, spec in attributes.items():
            owner = spec.owner or fragment.name
            existing = owners.get(attr_name)
            if existing and existing != owner:
                raise TemplateError(
                    f"Attribute '{attr_name}' already owned by '{existing}', conflict with '{owner}'."
                )
            owners[attr_name] = owner
        for key, value in resolved.items():
            context[key] = value
            injected[key] = value
    return injected


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
    declared_attribute_owners: Mapping[str, str] | None = None,
) -> FragmentRenderResult:
    """
    Render the selected fragments into ``output_dir`` and return the injected variables.
    """
    rendered_packages: list[str] = []
    written: list[Path] = []
    variable_injections: dict[str, list[str]] = {}
    providers: dict[str, list[str]] = {}
    owners: dict[str, str] = dict(declared_attribute_owners or {})

    if not isinstance(context, dict):
        raise TemplateError("Fragment rendering requires a mutable context dictionary.")

    fragments = _resolve_fragments(names, source_dir=source_dir)

    for fragment in fragments:
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

        if isinstance(fragment, FragmentDefinition):
            if fragment.attributes:
                resolved_attributes = fragment.resolve_attributes(overrides)
                for attr_name in fragment.attributes:
                    owner = fragment.attributes[attr_name].owner or fragment.name
                    existing = owners.get(attr_name)
                    if existing and existing != owner:
                        raise TemplateError(
                            f"Attribute '{attr_name}' already owned by '{existing}', conflict with '{owner}'."
                        )
                    owners[attr_name] = owner
                context.update(resolved_attributes)

            for key, value in fragment.context_defaults.items():
                context.setdefault(key, value)

            if fragment.context_injector is not None:
                fragment.context_injector(context, overrides)

            if fragment.should_render is not None:
                try:
                    if not fragment.should_render(context):
                        continue
                except Exception as exc:
                    # ``should_render`` is a user-authored predicate; a bug in
                    # it must not kill the whole render. Surface a warning so
                    # the failure isn't silent and fall through (fail-open) —
                    # the user sees the fragment render alongside the warning
                    # rather than losing output with no explanation.
                    warnings.warn(
                        f"Fragment '{fragment.name}' should_render() raised {exc!r};"
                        " rendering the fragment anyway.",
                        stacklevel=2,
                    )
        else:
            attributes = FRAGMENT_REGISTRY.attributes_for(fragment.name)
            resolver = FRAGMENT_REGISTRY.attribute_resolver_for(fragment.name)
            resolved_attributes = resolver.merge(overrides) if resolver else {}
            for attr_name, spec in attributes.items():
                owner = spec.owner or fragment.name
                existing = owners.get(attr_name)
                if existing and existing != owner:
                    raise TemplateError(
                        f"Attribute '{attr_name}' already owned by '{existing}', conflict with '{owner}'."
                    )
                owners[attr_name] = owner
            context.update(resolved_attributes)

            for key, value in getattr(fragment, "context_defaults", {}).items():
                context.setdefault(key, value)

            config = fragment.build_config(context, overrides=overrides)
            fragment.inject(config, context, overrides=overrides)
            try:
                if not fragment.should_render(config):
                    continue
            except Exception as exc:
                # Mirror the FragmentDefinition branch: warn and fall through
                # rather than losing the fragment to a buggy predicate.
                warnings.warn(
                    f"Fragment '{fragment.name}' should_render() raised {exc!r};"
                    " rendering the fragment anyway.",
                    stacklevel=2,
                )

        for piece in fragment.pieces:
            if not piece.is_enabled(context):
                continue
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
    "BaseFragment",
    "FragmentDefinition",
    "FragmentPiece",
    "FragmentRegistry",
    "FragmentRenderResult",
    "collect_fragment_attribute_defaults",
    "inject_fragment_attributes",
    "register_fragment",
    "render_fragments",
]
