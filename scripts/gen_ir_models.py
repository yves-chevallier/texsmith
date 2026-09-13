"""Generate ``src/texsmith/ir/model.py`` from tmark's IR JSON schema.

The schema (``crates/tmark-ir/schema/ir.json`` in the tmark repository) is
produced by schemars from the Rust types of ``tmark-ir``. This script turns
every definition into a frozen, slotted dataclass and writes, next to the
classes, the tables ``texsmith.ir.codec`` interprets (``FIELDS``, ``UNIONS``).
Design: ``specs/migration/python-ir-and-passes.md`` section 1.

Sources of the schema, in order:

* ``--schema PATH``: a schema file. CI uses the copy vendored under
  ``tests/fixtures/tmark-ir/ir.json`` (refreshed by
  ``scripts/refresh_tmark_fixtures.py``).
* the installed ``tmark`` wheel (``tmark.schema("ir")``), once it exists
  (phase 2 of the migration). The wheel then replaces the vendored file.

Usage::

    uv run python scripts/gen_ir_models.py --schema tests/fixtures/tmark-ir/ir.json \
        --version "$(cat tests/fixtures/tmark-ir/VERSION)"
    uv run python scripts/gen_ir_models.py --check ...   # exit 1 when model.py drifted

What the schema cannot express lives in the override tables below (serde
attributes schemars does not record, walk order, name clashes). Each entry is
checked against the schema so a stale override fails the generation. Any
schema construct outside the grammar in :func:`shape_of` raises
:class:`SchemaError` rather than degrading to ``Any``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "src" / "texsmith" / "ir" / "model.py"

# ---------------------------------------------------------------------------
# Overrides: knowledge the schema does not carry
# ---------------------------------------------------------------------------

#: The two node unions; their variants inherit ``Node`` (id, span, walked).
NODE_UNIONS = ("Block", "Inline")

#: Variant class names when the tag would clash or read poorly. Keyed by
#: ``(union, tag)``; the default name is the tag itself.
CLASS_NAMES: dict[tuple[str, str], str] = {
    ("Inline", "Span"): "SpanNode",  # ``Span`` is the byte range (Rust: SpanNode)
    ("Block", "Comment"): "CommentBlock",  # Rust shares one struct; Python has RawBlock-style names
    ("Target", "Document"): "DocumentTarget",  # ``Document`` is the root
    ("Row", "Data"): "DataRow",
    ("Column", "Leaf"): "LeafColumn",
    ("Column", "Group"): "ColumnGroup",
}

#: Enum member names when the value is not a readable identifier.
ENUM_MEMBERS: dict[str, dict[str, str]] = {
    "Align": {"l": "LEFT", "c": "CENTER", "r": "RIGHT", "j": "JUSTIFY"},
}

#: Fields tmark's pre-order walk (``walk.rs``) visits before the others of
#: the same class; the schema sorts properties alphabetically. Dataclass
#: field order is walk order for ``texsmith.ir.walk``.
FIELD_ORDER: dict[str, tuple[str, ...]] = {
    "Para": ("lead", "content"),
    "Admonition": ("title", "content"),
    "TableModel": ("rows", "footer"),
}

#: ``#[serde(default = "fn", skip_serializing_if = ...)]``: schemars drops a
#: default that the skip predicate would hide, so the value is only in Rust.
DEFAULTS: dict[tuple[str, str], Any] = {
    ("Cell", "rows"): 1,
    ("Cell", "cols"): 1,
}

#: ``Option<Option<String>>`` fields: absent is ``MISSING``, ``null`` is
#: ``None`` (``title: null`` opts out of title promotion).
DOUBLE_OPTIONS: frozenset[tuple[str, str]] = frozenset({("Keys", "title")})

#: ``any``-typed fields documented as JSON objects: typed ``dict[str, Any]``
#: with an empty default (skipped when empty, as serde does).
JSON_OBJECTS: frozenset[tuple[str, str]] = frozenset({("FrontMatter", "extra")})


class SchemaError(Exception):
    """A schema construct this generator does not know how to render."""


# ---------------------------------------------------------------------------
# Shapes: the type grammar shared with ``texsmith.ir.codec``
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Shape:
    """A decoded property type. ``kind`` is one of the codec's shape tags."""

    kind: str
    ref: str = ""  # class name for enum / record / union
    inner: tuple[Shape, ...] = ()

    def annotation(self) -> str:
        match self.kind:
            case "str":
                return "str"
            case "int":
                return "int"
            case "bool":
                return "bool"
            case "float":
                return "float"
            case "any":
                return "JsonValue"
            case "span":
                return "Span"
            case "enum" | "record" | "union":
                return self.ref
            case "list":
                return f"tuple[{self.inner[0].annotation()}, ...]"
            case "tuple":
                return "tuple[" + ", ".join(s.annotation() for s in self.inner) + "]"
            case "map":
                return f"dict[str, {self.inner[0].annotation()}]"
            case "opt":
                return f"{self.inner[0].annotation()} | None"
        raise SchemaError(f"unknown shape kind {self.kind!r}")

    def literal(self) -> str:
        """Source of the shape tuple ``codec`` interprets."""
        match self.kind:
            case "enum" | "record" | "union":
                return f'("{self.kind}", {self.ref})'
            case "list" | "map" | "opt":
                return f'("{self.kind}", {self.inner[0].literal()})'
            case "tuple":
                return '("tuple", (' + ", ".join(s.literal() for s in self.inner) + ",))"
        return f'("{self.kind}",)'

    def implicit_default(self) -> tuple[str, bool]:
        """``(source, is_factory)`` of the value an absent field takes."""
        match self.kind:
            case "str":
                return '""', False
            case "int":
                return "0", False
            case "bool":
                return "False", False
            case "float":
                return "0.0", False
            case "any" | "opt":
                return "None", False
            case "span":
                return "NO_SPAN", False
            case "list" | "tuple":
                return "()", False
            case "map":
                return "dict", True
            case "record":
                return self.ref, True
        raise SchemaError(f"a {self.kind} field needs a schema default or must be required")


@dataclass
class FieldSpec:
    name: str
    shape: Shape
    required: bool
    default_src: str  # Python source of the default (or of the factory)
    is_factory: bool
    policy: str  # "required" | "always" | "skip"
    annotation: str
    description: str = ""
    meta: bool = False  # part of the flattened Meta (id, span)


@dataclass
class ClassSpec:
    name: str
    base: str  # "Record", "Node", or a union base class name
    doc: str
    fields: list[FieldSpec]
    tag: str | None = None  # variant tag in its union
    union: str | None = None
    has_meta: bool = False
    deps: set[str] = field(default_factory=set)  # classes needed at runtime


@dataclass
class EnumSpec:
    name: str
    doc: str
    members: list[tuple[str, str]]  # (member, value)


@dataclass
class UnionSpec:
    name: str
    doc: str
    variants: list[ClassSpec]


@dataclass
class Model:
    span_names: list[str]
    span_fields: tuple[str, ...]
    enums: dict[str, EnumSpec]
    unions: dict[str, UnionSpec]
    records: dict[str, ClassSpec]  # every dataclass with fields, variants included
    root: str


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _is_span(defn: dict[str, Any]) -> bool:
    items = defn.get("items")
    return (
        defn.get("type") == "array"
        and isinstance(items, dict)
        and items.get("type") == "integer"
        and defn.get("minItems") == defn.get("maxItems")
        and isinstance(defn.get("minItems"), int)
    )


def _span_field_names(defn: dict[str, Any]) -> tuple[str, ...]:
    match = re.search(r"\[([a-z_, ]+)\]", defn.get("description", ""))
    if not match:
        raise SchemaError("a span definition must document its fields as `[a, b, c]`")
    names = tuple(part.strip() for part in match.group(1).split(","))
    if len(names) != defn["minItems"]:
        raise SchemaError(f"span documents {len(names)} names for {defn['minItems']} items")
    return names


def _enum_values(defn: dict[str, Any]) -> list[str] | None:
    if "enum" in defn and defn.get("type", "string") == "string":
        return list(defn["enum"])
    variants = defn.get("oneOf")
    if variants and all("enum" in v and v.get("type") == "string" for v in variants):
        return [value for v in variants for value in v["enum"]]
    return None


def _tag_of(variant: dict[str, Any], tag_key: str) -> str | None:
    tag = variant.get("properties", {}).get(tag_key, {})
    values = tag.get("enum")
    if variant.get("type") == "object" and isinstance(values, list) and len(values) == 1:
        return str(values[0])
    return None


def _classify(name: str, defn: dict[str, Any], tag_key: str) -> str:
    if _is_span(defn):
        return "span"
    if _enum_values(defn) is not None:
        return "enum"
    variants = defn.get("oneOf")
    if variants and all(_tag_of(v, tag_key) is not None for v in variants):
        return "union"
    if defn.get("type") == "object" and "additionalProperties" not in defn:
        return "record"
    raise SchemaError(f"definition {name!r}: unsupported construct {sorted(defn)}")


def _member_name(value: str) -> str:
    member = re.sub(r"\W", "_", value).upper()
    if not member or member[0].isdigit():
        member = "V_" + member
    return member


def _docstring(text: str, fallback: str) -> str:
    text = text.strip().split("\n\n", 1)[0].replace("\n", " ").strip()
    text = text.replace("\\", "\\\\").replace('"""', "'''")
    return text or fallback


# ---------------------------------------------------------------------------
# Property shapes
# ---------------------------------------------------------------------------


class Generator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self.defs: dict[str, Any] = schema.get("definitions", {})
        self.tag_key = "type"
        self.kinds = {name: _classify(name, d, self.tag_key) for name, d in self.defs.items()}
        self.class_names: dict[str, str] = {}  # definition or (union.tag) -> class name
        self.used_overrides: set[Any] = set()

    # -- shapes -------------------------------------------------------------

    def ref_shape(self, ref: str) -> Shape:
        name = ref.rsplit("/", 1)[-1]
        if name not in self.kinds:
            raise SchemaError(f"reference to unknown definition {name!r}")
        kind = self.kinds[name]
        if kind == "span":
            return Shape("span")
        return Shape(kind, ref=name)

    def shape_of(self, prop: dict[str, Any], where: str) -> Shape:
        keys = set(prop) - {"description", "default"}
        if "$ref" in prop:
            return self.ref_shape(prop["$ref"])
        if keys == {"allOf"} and len(prop["allOf"]) == 1:
            return self.shape_of(prop["allOf"][0], where)
        if "anyOf" in prop:
            parts = prop["anyOf"]
            nulls = [p for p in parts if p == {"type": "null"}]
            others = [p for p in parts if p != {"type": "null"}]
            if len(parts) == 2 and len(nulls) == 1:
                return Shape("opt", inner=(self.shape_of(others[0], where),))
            raise SchemaError(f"{where}: anyOf other than `T | null`")
        kind = prop.get("type")
        if isinstance(kind, list):
            others = [t for t in kind if t != "null"]
            if len(kind) == 2 and len(others) == 1:
                inner = self.shape_of({**prop, "type": others[0]}, where)
                return Shape("opt", inner=(inner,))
            raise SchemaError(f"{where}: type list other than `[T, null]`")
        if kind == "array":
            items = prop.get("items")
            if isinstance(items, list):
                if prop.get("minItems") != len(items) or prop.get("maxItems") != len(items):
                    raise SchemaError(f"{where}: tuple items without fixed length")
                inner = tuple(self.shape_of(i, f"{where}[{n}]") for n, i in enumerate(items))
                return Shape("tuple", inner=inner)
            if isinstance(items, dict):
                return Shape("list", inner=(self.shape_of(items, f"{where}[]"),))
            raise SchemaError(f"{where}: array without items")
        if kind == "object":
            extra = prop.get("additionalProperties")
            if isinstance(extra, dict) and "properties" not in prop:
                return Shape("map", inner=(self.shape_of(extra, f"{where}{{}}"),))
            raise SchemaError(f"{where}: anonymous object; make it a definition")
        if kind == "string":
            if "enum" in prop:
                raise SchemaError(f"{where}: anonymous enum; make it a definition")
            return Shape("str")
        if kind == "integer":
            return Shape("int")
        if kind == "boolean":
            return Shape("bool")
        if kind == "number":
            return Shape("float")
        if kind is None and not keys:
            return Shape("any")
        raise SchemaError(f"{where}: unsupported property schema {sorted(prop)}")

    # -- defaults -----------------------------------------------------------

    def default_source(self, shape: Shape, value: Any, where: str) -> tuple[str, bool]:
        """Source for a schema ``default`` value of the given shape."""
        match shape.kind:
            case "str" | "int" | "bool" | "float":
                return repr(value), False
            case "enum":
                for member, enum_value in self.enum_members(shape.ref):
                    if enum_value == value:
                        return f"{shape.ref}.{member}", False
                raise SchemaError(f"{where}: default {value!r} is not a {shape.ref} value")
            case "span":
                if all(v == 0 for v in value):
                    return "NO_SPAN", False
                return "Span(" + ", ".join(repr(v) for v in value) + ")", False
            case "record":
                # The default of a struct field is its ``Default`` instance,
                # which serialises to the schema default; a test checks it.
                return shape.ref, True
            case "list" | "tuple":
                if value == []:
                    return "()", False
            case "map":
                if value == {}:
                    return "dict", True
            case "opt":
                if value is None:
                    return "None", False
        raise SchemaError(f"{where}: cannot render default {value!r} for a {shape.kind}")

    def enum_members(self, name: str) -> list[tuple[str, str]]:
        values = _enum_values(self.defs[name])
        assert values is not None
        override = ENUM_MEMBERS.get(name)
        if override is not None:
            if set(override) != set(values):
                raise SchemaError(f"ENUM_MEMBERS[{name!r}] does not match values {values}")
            self.used_overrides.add(("enum", name))
            return [(override[v], v) for v in values]
        members = [(_member_name(v), v) for v in values]
        if len({m for m, _ in members}) != len(members):
            raise SchemaError(f"enum {name!r}: member names clash; add ENUM_MEMBERS")
        return members

    # -- classes ------------------------------------------------------------

    def field_specs(self, owner: str, defn: dict[str, Any]) -> tuple[list[FieldSpec], bool]:
        props: dict[str, Any] = defn.get("properties", {})
        required = set(defn.get("required", []))
        has_meta = self._has_meta(props)
        specs: list[FieldSpec] = []
        for name, prop in props.items():
            if name == self.tag_key and owner in self.class_names_of_variants:
                continue
            where = f"{owner}.{name}"
            shape = self.shape_of(prop, where)
            is_required = name in required
            description = prop.get("description", "")
            if "Some(None)" in description and (owner, name) not in DOUBLE_OPTIONS:
                raise SchemaError(f"{where}: double option not listed in DOUBLE_OPTIONS")
            annotation = shape.annotation()
            if (owner, name) in DOUBLE_OPTIONS:
                if shape != Shape("opt", inner=(Shape("str"),)) or is_required:
                    raise SchemaError(f"{where}: DOUBLE_OPTIONS entry is not an optional string")
                self.used_overrides.add(("double", owner, name))
                annotation = "str | None | Missing"
                specs.append(
                    FieldSpec(name, shape, False, "MISSING", False, "skip", annotation, description)
                )
                continue
            if (owner, name) in JSON_OBJECTS:
                if shape.kind != "any" or is_required:
                    raise SchemaError(f"{where}: JSON_OBJECTS entry is not an optional any")
                self.used_overrides.add(("object", owner, name))
                specs.append(
                    FieldSpec(
                        name,
                        shape,
                        False,
                        "dict",
                        True,
                        "skip",
                        "dict[str, JsonValue]",
                        description,
                    )
                )
                continue
            if is_required:
                specs.append(FieldSpec(name, shape, True, "", False, "required", annotation))
                continue
            if "default" in prop:
                src, factory = self.default_source(shape, prop["default"], where)
                policy = "always"
            elif (owner, name) in DEFAULTS:
                self.used_overrides.add(("default", owner, name))
                src, factory, policy = repr(DEFAULTS[(owner, name)]), False, "skip"
            else:
                src, factory = shape.implicit_default()
                policy = "skip"
            meta = has_meta and name in ("id", "span")
            specs.append(
                FieldSpec(name, shape, False, src, factory, policy, annotation, description, meta)
            )
        return self._ordered(owner, specs), has_meta

    def _has_meta(self, props: dict[str, Any]) -> bool:
        ident = props.get("id", {})
        span = props.get("span", {})
        return (
            ident.get("type") == "integer"
            and ident.get("default") == 0
            and span.get("default") == [0, 0, 0]
            and self.shape_of(span, "span") == Shape("span")
        )

    def _ordered(self, owner: str, specs: list[FieldSpec]) -> list[FieldSpec]:
        first = FIELD_ORDER.get(owner, ())
        names = {s.name for s in specs}
        for name in first:
            if name not in names:
                raise SchemaError(f"FIELD_ORDER[{owner!r}] names unknown field {name!r}")
        if first:
            self.used_overrides.add(("order", owner))

        def key(spec: FieldSpec) -> tuple[int, int, int, str]:
            group = 2 if spec.meta else (0 if spec.required else 1)
            rank = first.index(spec.name) if spec.name in first else len(first)
            return (group, rank, 0, spec.name)

        return sorted(specs, key=key)

    def build(self) -> Model:
        spans = sorted(n for n, k in self.kinds.items() if k == "span")
        if not spans:
            raise SchemaError("no span definition (array of fixed integers)")
        span_fields = _span_field_names(self.defs[spans[0]])
        for name in spans[1:]:
            if _span_field_names(self.defs[name]) != span_fields:
                raise SchemaError(f"span definitions differ: {spans[0]} vs {name}")

        enums = {
            name: EnumSpec(name, _docstring(self.defs[name].get("description", ""), name), [])
            for name, kind in sorted(self.kinds.items())
            if kind == "enum"
        }
        for spec in enums.values():
            spec.members = self.enum_members(spec.name)

        # Class names: definitions first, then union variants (with overrides).
        self.class_names_of_variants: set[str] = set()
        taken = set(spans) | set(enums) | {"Missing", "Node", "Record", "JsonValue"}
        root_name = str(self.schema.get("title") or "Document")
        taken.add(root_name)
        for name, kind in self.kinds.items():
            if kind in ("record", "union"):
                if name in taken:
                    raise SchemaError(f"class name {name!r} clashes")
                taken.add(name)
        variant_names: dict[tuple[str, str], str] = {}
        for union, kind in sorted(self.kinds.items()):
            if kind != "union":
                continue
            for variant in self.defs[union]["oneOf"]:
                tag = _tag_of(variant, self.tag_key)
                assert tag is not None
                name = CLASS_NAMES.get((union, tag), tag)
                if (union, tag) in CLASS_NAMES:
                    self.used_overrides.add(("name", union, tag))
                if name in taken:
                    raise SchemaError(
                        f"variant {union}.{tag}: class name {name!r} clashes; add CLASS_NAMES"
                    )
                taken.add(name)
                variant_names[(union, tag)] = name
                self.class_names_of_variants.add(name)

        records: dict[str, ClassSpec] = {}
        unions: dict[str, UnionSpec] = {}
        for union, kind in sorted(self.kinds.items()):
            if kind != "union":
                continue
            spec = UnionSpec(union, _docstring(self.defs[union].get("description", ""), union), [])
            for variant in self.defs[union]["oneOf"]:
                tag = _tag_of(variant, self.tag_key)
                assert tag is not None
                name = variant_names[(union, tag)]
                fields_, has_meta = self.field_specs(name, variant)
                if union in NODE_UNIONS and not has_meta:
                    raise SchemaError(f"node variant {name} has no id/span")
                doc = _docstring(variant.get("description", ""), f"``{tag}`` variant of {union}.")
                cls = ClassSpec(name, union, doc, fields_, tag=tag, union=union, has_meta=has_meta)
                cls.deps.add(union)
                spec.variants.append(cls)
                records[name] = cls
            unions[union] = spec
        for name, kind in sorted(self.kinds.items()):
            if kind != "record":
                continue
            fields_, has_meta = self.field_specs(name, self.defs[name])
            doc = _docstring(self.defs[name].get("description", ""), f"{name}.")
            records[name] = ClassSpec(name, "Record", doc, fields_, has_meta=has_meta)
        fields_, has_meta = self.field_specs(root_name, self.schema)
        # The root description opens with schemars' "generated, do not edit"
        # note, which belongs to the schema file, not to the class.
        root_doc = self.schema.get("description", "").split("do not edit.", 1)[-1]
        records[root_name] = ClassSpec(
            root_name,
            "Record",
            _docstring(root_doc, f"{root_name}: the schema root."),
            fields_,
            has_meta=has_meta,
        )
        for cls in records.values():
            for f in cls.fields:
                if f.is_factory and f.default_src in records:
                    cls.deps.add(f.default_src)
        self._check_overrides()
        return Model(spans, span_fields, enums, unions, records, root_name)

    def _check_overrides(self) -> None:
        expected: set[Any] = set()
        expected |= {("name", u, t) for (u, t) in CLASS_NAMES}
        expected |= {("enum", n) for n in ENUM_MEMBERS}
        expected |= {("order", o) for o in FIELD_ORDER}
        expected |= {("default", o, n) for (o, n) in DEFAULTS}
        expected |= {("double", o, n) for (o, n) in DOUBLE_OPTIONS}
        expected |= {("object", o, n) for (o, n) in JSON_OBJECTS}
        stale = expected - self.used_overrides
        if stale:
            raise SchemaError(f"overrides no longer match the schema: {sorted(map(str, stale))}")


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------


def _topological(records: dict[str, ClassSpec], unions: dict[str, UnionSpec]) -> list[str]:
    pending = dict(records)
    emitted: set[str] = set(unions)  # union bases are emitted before the classes
    order: list[str] = []
    while pending:
        ready = sorted(n for n, c in pending.items() if c.deps - {n} <= emitted)
        if not ready:
            raise SchemaError(f"cyclic default dependencies among {sorted(pending)}")
        for name in ready:
            order.append(name)
            emitted.add(name)
            del pending[name]
    return order


def render(model: Model, version: str, schema_hash: str) -> str:
    out: list[str] = []
    w = out.append
    w('"""TeXSmith IR models generated from the tmark IR schema. Do not edit.\n')
    w(f"tmark version: {version}\n")
    w(f"schema sha256: {schema_hash}\n\n")
    w("Regenerate with ``scripts/gen_ir_models.py`` (``--check`` in CI). Every node is a\n")
    w("frozen, slotted dataclass; ``id`` and ``span`` do not take part in equality or\n")
    w("hashing (tmark rule 3). ``FIELDS`` and ``UNIONS`` drive :mod:`texsmith.ir.codec`.\n")
    w('"""\n\n')
    w("from __future__ import annotations\n\n")
    w("from dataclasses import dataclass, field\n")
    w("from enum import Enum\n")
    w("from typing import Any, ClassVar, Final, Literal, NamedTuple, TypeAlias\n\n")
    w("from texsmith.diagnostics.model import NO_SPAN, Span\n\n\n")
    w(f"TMARK_VERSION: Final = {version!r}\n")
    w(f"SCHEMA_HASH: Final = {schema_hash!r}\n\n")
    w("#: A JSON value the schema leaves untyped (front-matter blobs).\n")
    w("JsonValue: TypeAlias = Any\n\n\n")
    w("class Missing:\n")
    w('    """Type of :data:`MISSING`: a key absent from the JSON (not ``null``)."""\n\n')
    w("    __slots__ = ()\n\n")
    w("    def __repr__(self) -> str:\n")
    w('        return "MISSING"\n\n\n')
    w("MISSING: Final = Missing()\n\n\n")

    # Span: defined once, in the diagnostics package. The IR must not emit a
    # second definition (``texsmith/diagnostics/model.py`` header).
    span = model.span_names[0]
    for alias in model.span_names[1:]:
        w(f"{alias}: TypeAlias = {span}\n")
    w("\n\n")

    # Enums.
    for enum in model.enums.values():
        w("class " + enum.name + "(Enum):\n")
        w(f'    """{enum.doc}"""\n\n')
        for member, value in enum.members:
            w(f"    {member} = {value!r}\n")
        w("\n\n")

    # Bases.
    w("@dataclass(frozen=True, slots=True)\n")
    w("class Record:\n")
    w('    """A supporting structure without identity (list items, cells, front matter)."""\n\n\n')
    w("@dataclass(frozen=True, slots=True)\n")
    w("class Node:\n")
    w('    """A block or inline: identity (``id``) and source ``span``, ignored by ``==``."""\n\n')
    w("    id: int = field(default=0, compare=False, kw_only=True)\n")
    w(f"    span: {span} = field(default=NO_SPAN, compare=False, kw_only=True)\n\n\n")
    for union in model.unions.values():
        base = "Node" if union.name in NODE_UNIONS else "Record"
        w("@dataclass(frozen=True, slots=True)\n")
        w(f"class {union.name}({base}):\n")
        w(f'    """{union.doc}"""\n\n\n')

    # Records and variants.
    for name in _topological(model.records, model.unions):
        cls = model.records[name]
        w("@dataclass(frozen=True, slots=True)\n")
        w(f"class {cls.name}({cls.base}):\n")
        w(f'    """{cls.doc}"""\n\n')
        if cls.tag is not None:
            w(f'    type: ClassVar[Literal["{cls.tag}"]] = "{cls.tag}"\n')
        inherited_meta = cls.union in NODE_UNIONS
        for f in cls.fields:
            if f.meta and inherited_meta:
                continue
            if f.required:
                w(f"    {f.name}: {f.annotation}\n")
            elif f.meta:
                w(f"    {f.name}: {f.annotation} = field(default={f.default_src}, ")
                w("compare=False, kw_only=True)\n")
            elif f.is_factory:
                w(f"    {f.name}: {f.annotation} = field(default_factory={f.default_src})\n")
            else:
                w(f"    {f.name}: {f.annotation} = {f.default_src}\n")
        if cls.tag is None and not cls.fields:
            w("    pass\n")
        w("\n\n")

    # Unions for pyright.
    for union in model.unions.values():
        members = " | ".join(v.name for v in union.variants)
        w(f"Any{union.name}: TypeAlias = {members}\n")
    w("\n\n")

    # Codec tables.
    w("class FieldSpec(NamedTuple):\n")
    w('    """One JSON property of a record, as ``texsmith.ir.codec`` reads it."""\n\n')
    w("    name: str\n")
    w("    shape: tuple[Any, ...]\n")
    w('    policy: str  # "required" | "always" (schema default) | "skip" (at default)\n')
    w("    default: Any  # the default value, or its zero-argument factory\n")
    w("    factory: bool = False\n\n\n")
    w('TAG: Final = "type"\n\n')
    w("#: Tag to variant class, per union base class.\n")
    w("UNIONS: Final[dict[type, dict[str, type]]] = {\n")
    for union in model.unions.values():
        w(f"    {union.name}: {{\n")
        for v in union.variants:
            w(f'        "{v.tag}": {v.name},\n')
        w("    },\n")
    w("}\n\n")
    w("#: JSON properties of every record and variant, in dataclass order.\n")
    w("FIELDS: Final[dict[type, tuple[FieldSpec, ...]]] = {\n")
    for name in sorted(model.records):
        cls = model.records[name]
        w(f"    {cls.name}: (\n")
        for f in cls.fields:
            default = "None" if f.required else f.default_src
            factory = ", True" if f.is_factory else ""
            w(
                f'        FieldSpec("{f.name}", {f.shape.literal()}, "{f.policy}", {default}{factory}),\n'
            )
        w("    ),\n")
    w("}\n\n")
    w(f"ROOT: Final = {model.root}\n\n")

    names_all = sorted(
        {"Missing", "MISSING", "NO_SPAN", "Node", "Record", "FieldSpec", "FIELDS", "UNIONS"}
        | {"TAG", "ROOT", "TMARK_VERSION", "SCHEMA_HASH", "JsonValue"}
        | set(model.span_names)
        | set(model.enums)
        | set(model.unions)
        | {f"Any{u}" for u in model.unions}
        | set(model.records)
    )
    w("__all__ = [\n")
    for name in names_all:
        w(f'    "{name}",\n')
    w("]\n")
    return "".join(out)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def canonical_hash(schema: dict[str, Any]) -> str:
    """sha256 of the schema as compact JSON with sorted keys (format-independent).

    The root ``description`` is left out: the file written by tmark's
    ``schema`` example prefixes it with a "generated, do not edit" note that
    the in-process ``tmark.schema("ir")`` does not carry. Keep in sync with
    ``texsmith.ir.codec.canonical_hash``.
    """
    shape = {key: value for key, value in schema.items() if key != "description"}
    text = json.dumps(shape, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_schema(path: Path | None) -> tuple[dict[str, Any], str | None]:
    """The schema and, when it comes from the wheel, the wheel's version."""
    if path is not None:
        # The vendored file carries no version: name the installed wheel's
        # when there is one, so a file-based run and a wheel-based run agree.
        try:
            import tmark  # type: ignore[import-not-found]

            version = getattr(tmark, "__version__", None)
        except ImportError:
            version = None
        return json.loads(path.read_text(encoding="utf-8")), version
    try:
        import tmark  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit("tmark is not installed: pass --schema PATH") from exc
    schema = tmark.schema("ir")
    if isinstance(schema, str):
        schema = json.loads(schema)
    return schema, getattr(tmark, "__version__", None)


def generate(schema: dict[str, Any], version: str) -> str:
    model = Generator(schema).build()
    return render(model, version, canonical_hash(schema))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--schema", type=Path, help="schema file (default: the tmark wheel)")
    parser.add_argument("--version", help="tmark version named in the header")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="exit 1 if the output differs")
    args = parser.parse_args(argv)

    schema, wheel_version = load_schema(args.schema)
    version = args.version or wheel_version or "unknown"
    try:
        text = generate(schema, version)
    except SchemaError as exc:
        sys.stderr.write(f"gen_ir_models: {exc}\n")
        return 2
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != text:
            sys.stderr.write(f"{args.output} is out of date; rerun scripts/gen_ir_models.py\n")
            return 1
        return 0
    args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
