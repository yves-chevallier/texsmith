"""JSON codec for the generated IR models (:mod:`texsmith.ir.model`).

The producer of the JSON is the pinned ``tmark`` wheel, so the decoder trusts
the shape: it checks the variant tag, the required keys and the scalar types,
and names the JSON path in :class:`IRDecodeError` when they disagree.
Unknown keys are ignored, as serde does (``tmark.parse`` adds ``tmark`` and
``diagnostics`` at the root).

``encode_document`` reproduces serde's output byte for byte in structure: a
property with a schema default is always written, one without is skipped at
its default (``skip_serializing_if``), so ``encode(decode(x)) == x`` for any
``tmark`` output. :func:`structural` is the twin of Rust ``structural_json``:
no ids, spans, ``*_span`` fields, spelling-only fields or absent values — what
the conformance fixtures store.

The tables interpreted here (``FIELDS``, ``UNIONS``) are generated with the
classes by ``scripts/gen_ir_models.py``. A shape is a tuple whose first item
names the kind:

* scalars ``("str",)``, ``("int",)``, ``("bool",)``, ``("float",)``,
  ``("any",)`` (untyped JSON), ``("span",)`` (``[file, start, end]``);
* ``("enum", Cls)``, ``("record", Cls)``, ``("union", Base)`` (tagged by
  ``TAG``);
* ``("list", inner)``, ``("tuple", (inner, ...))`` (fixed length),
  ``("map", inner)`` (string keys), ``("opt", inner)`` (``null`` allowed).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
import hashlib
import json
from typing import Any, TypeVar

from texsmith.ir import model
from texsmith.ir.model import FIELDS, ROOT, SCHEMA_HASH, TAG, TMARK_VERSION, UNIONS, Node, Record


__all__ = [
    "SUGAR_FIELDS",
    "IRDecodeError",
    "canonical_hash",
    "decode",
    "decode_document",
    "encode",
    "encode_document",
    "format_path",
    "structural",
    "wheel_schema_mismatch",
]

JsonPath = tuple[str | int, ...]
Shape = tuple[Any, ...]
R = TypeVar("R", bound=Node | Record)

#: Fields that record which spelling was written rather than what the node is
#: (``tmark_ir::SUGAR_FIELDS``): ``Caption.position``, ``Ref.bracketed``.
SUGAR_FIELDS = frozenset({"position", "bracketed"})

_SPAN_FIELDS = tuple(f.name for f in fields(model.Span))
_VARIANT_TAG: dict[type, str] = {
    cls: tag for members in UNIONS.values() for tag, cls in members.items()
}


class IRDecodeError(ValueError):
    """The JSON does not have the shape of the schema, at ``path``."""

    def __init__(self, path: JsonPath, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{format_path(path)}: {message}")


def format_path(path: JsonPath) -> str:
    """``$.blocks[0].content[2].text`` for ``("blocks", 0, "content", 2, "text")``."""
    out = "$"
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


# ---------------------------------------------------------------------------
# Field tables
# ---------------------------------------------------------------------------

# (name, shape, policy, default, factory) per class; defaults produced by a
# factory are rebuilt per use so a ``dict`` default is never shared.
_Compiled = tuple[tuple[str, Shape, str, Any, bool], ...]
_COMPILED: dict[type, _Compiled] = {}


def _compiled(cls: type) -> _Compiled:
    table = _COMPILED.get(cls)
    if table is None:
        try:
            specs = FIELDS[cls]
        except KeyError:
            raise TypeError(f"{cls.__name__} is not an IR record") from None
        table = tuple((s.name, s.shape, s.policy, s.default, s.factory) for s in specs)
        _COMPILED[cls] = table
    return table


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------


def _fail(path: JsonPath, expected: str, value: Any) -> IRDecodeError:
    return IRDecodeError(path, f"expected {expected}, got {type(value).__name__}")


def _decode(value: Any, shape: Shape, path: JsonPath) -> Any:
    kind = shape[0]
    if kind == "str":
        if not isinstance(value, str):
            raise _fail(path, "a string", value)
        return value
    if kind == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise _fail(path, "an integer", value)
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            raise _fail(path, "a boolean", value)
        return value
    if kind == "float":
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise _fail(path, "a number", value)
        return float(value)
    if kind == "any":
        return value
    if kind == "span":
        if not isinstance(value, list) or len(value) != len(_SPAN_FIELDS):
            raise _fail(path, f"a span of {len(_SPAN_FIELDS)} integers", value)
        return model.Span(*value)
    if kind == "enum":
        try:
            return shape[1](value)
        except ValueError:
            raise IRDecodeError(path, f"{value!r} is not a {shape[1].__name__}") from None
    if kind == "record":
        return _decode_record(shape[1], value, path)
    if kind == "union":
        return _decode_union(shape[1], value, path)
    if kind == "list":
        if not isinstance(value, list):
            raise _fail(path, "an array", value)
        inner = shape[1]
        return tuple(_decode(item, inner, (*path, i)) for i, item in enumerate(value))
    if kind == "tuple":
        inners = shape[1]
        if not isinstance(value, list) or len(value) != len(inners):
            raise _fail(path, f"an array of {len(inners)} items", value)
        return tuple(
            _decode(item, inner, (*path, i))
            for i, (item, inner) in enumerate(zip(value, inners, strict=True))
        )
    if kind == "map":
        if not isinstance(value, Mapping):
            raise _fail(path, "an object", value)
        inner = shape[1]
        return {key: _decode(item, inner, (*path, key)) for key, item in value.items()}
    if kind == "opt":
        return None if value is None else _decode(value, shape[1], path)
    raise IRDecodeError(path, f"unknown shape {kind!r} in the generated tables")


def _decode_record(cls: type[R], value: Any, path: JsonPath) -> R:
    if not isinstance(value, Mapping):
        raise _fail(path, f"an object ({cls.__name__})", value)
    kwargs: dict[str, Any] = {}
    for name, shape, policy, default, factory in _compiled(cls):
        if name in value:
            kwargs[name] = _decode(value[name], shape, (*path, name))
        elif policy == "required":
            # Structural JSON (the conformance fixtures) drops absent-equivalent
            # values even for required keys: an empty ``src`` string, an empty
            # array. Those shapes have an absent value; a missing ``level``,
            # ``kind`` or ``target`` has none and is an error.
            absent = _ABSENT.get(shape[0], _NO_ABSENT)
            if absent is _NO_ABSENT:
                raise IRDecodeError(path, f"{cls.__name__} misses the required key {name!r}")
            kwargs[name] = absent() if callable(absent) else absent
        else:
            kwargs[name] = default() if factory else default
    return cls(**kwargs)


_NO_ABSENT = object()
_ABSENT: dict[str, Any] = {"str": "", "list": (), "map": dict, "opt": None, "any": None}


def _decode_union(base: type, value: Any, path: JsonPath) -> Any:
    if not isinstance(value, Mapping):
        raise _fail(path, f"a tagged object ({base.__name__})", value)
    tag = value.get(TAG)
    if tag is None:
        raise IRDecodeError(path, f"{base.__name__} object without a {TAG!r} tag")
    cls = UNIONS[base].get(tag)
    if cls is None:
        raise IRDecodeError((*path, TAG), f"{tag!r} is not a {base.__name__} variant")
    return _decode_record(cls, value, path)


def decode(data: Any, cls: type[R]) -> R:
    """Decode ``data`` as ``cls``: a record, a node class, or a union base."""
    if cls in UNIONS:
        return _decode_union(cls, data, ())
    return _decode_record(cls, data, ())


def decode_document(data: Mapping[str, Any]) -> model.Document:
    """Decode a ``Document`` (the output of ``tmark parse`` / ``tmark.parse``).

    The root ``tmark`` version, when present, must be compatible with the one
    the models were generated for (same major; same minor while major is 0).
    """
    if not isinstance(data, Mapping):
        raise _fail((), "a document object", data)
    version = data.get("tmark")
    if version is not None and not _compatible(str(version), TMARK_VERSION):
        raise IRDecodeError(
            ("tmark",),
            f"document produced by tmark {version}, models generated for {TMARK_VERSION}",
        )
    return _decode_record(ROOT, data, ())


def _compatible(produced: str, generated: str) -> bool:
    a = _version_parts(produced)
    b = _version_parts(generated)
    if not a or not b:
        return True  # an unparsable version is not a reason to refuse a document
    return a[:1] == b[:1] and (a[0] != 0 or a[:2] == b[:2])


def _version_parts(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.strip().split("+", 1)[0].split("."):
        digits = ""
        for ch in piece:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def _encode(value: Any, shape: Shape) -> Any:
    kind = shape[0]
    if kind in ("str", "int", "bool", "float", "any"):
        return value
    if kind == "span":
        return [getattr(value, name) for name in _SPAN_FIELDS]
    if kind == "enum":
        return value.value
    if kind in ("record", "union"):
        return _encode_record(value)
    if kind == "list":
        inner = shape[1]
        return [_encode(item, inner) for item in value]
    if kind == "tuple":
        return [_encode(item, inner) for item, inner in zip(value, shape[1], strict=True)]
    if kind == "map":
        inner = shape[1]
        return {key: _encode(value[key], inner) for key in sorted(value)}
    if kind == "opt":
        return None if value is None else _encode(value, shape[1])
    raise TypeError(f"unknown shape {kind!r} in the generated tables")


def _encode_record(obj: Any) -> dict[str, Any]:
    cls = type(obj)
    out: dict[str, Any] = {}
    tag = _VARIANT_TAG.get(cls)
    if tag is not None:
        out[TAG] = tag
    for name, shape, policy, default, factory in _compiled(cls):
        value = getattr(obj, name)
        if policy == "skip" and value == (default() if factory else default):
            continue
        out[name] = _encode(value, shape)
    return out


def encode(obj: Node | Record) -> dict[str, Any]:
    """The JSON object of a node or record, as serde writes it."""
    return _encode_record(obj)


def encode_document(doc: model.Document) -> dict[str, Any]:
    """The JSON of a document, as ``tmark parse`` prints it (ids and spans included)."""
    return _encode_record(doc)


# ---------------------------------------------------------------------------
# Structural view
# ---------------------------------------------------------------------------


def structural(obj: Node | Record) -> dict[str, Any]:
    """The JSON of ``obj`` without identity and spelling (Rust ``structural_json``).

    Drops the root ``file``, every ``span``, the ``id`` next to a ``span``
    (``attrs.id`` is content and stays), every ``*_span`` field, the
    :data:`SUGAR_FIELDS`, and absent-equivalent values (``null``, empty
    strings, arrays and objects; booleans and numbers stay).
    """
    data = _encode_record(obj)
    if isinstance(obj, ROOT):
        data.pop("file", None)
    return _strip_identity(data)


def _strip_identity(value: Any) -> Any:
    if isinstance(value, dict):
        node = "span" in value
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key == "span" or (node and key == "id") or key.endswith("_span"):
                continue
            if key in SUGAR_FIELDS:
                continue
            stripped = _strip_identity(item)
            if not _is_absent(stripped):
                out[key] = stripped
        return out
    if isinstance(value, list):
        return [_strip_identity(item) for item in value]
    return value


def _is_absent(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str | list | dict) and not value


# ---------------------------------------------------------------------------
# Schema drift against the installed wheel
# ---------------------------------------------------------------------------


def canonical_hash(schema: Mapping[str, Any]) -> str:
    """sha256 of a schema as compact JSON with sorted keys (the generator's hash).

    The root ``description`` is left out: the schema file carries a
    "generated, do not edit" note there that ``tmark.schema("ir")`` does not.
    Keep in sync with ``scripts/gen_ir_models.py``.
    """
    shape = {key: value for key, value in schema.items() if key != "description"}
    text = json.dumps(shape, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wheel_schema_mismatch() -> str | None:
    """A message when an installed ``tmark`` wheel ships another IR schema, else ``None``.

    ``None`` too when no wheel is importable or it has no ``schema`` function:
    the vendored schema then stands (phase 2 of the migration).
    """
    try:
        import tmark  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        schema = tmark.schema("ir")
        version = getattr(tmark, "__version__", "?")
    except Exception:
        return None
    if isinstance(schema, str):
        schema = json.loads(schema)
    actual = canonical_hash(schema)
    if actual == SCHEMA_HASH:
        return None
    return (
        f"texsmith.ir.model was generated for tmark {TMARK_VERSION} (schema {SCHEMA_HASH[:12]}), "
        f"but the installed tmark {version} ships schema {actual[:12]}; "
        "rerun scripts/gen_ir_models.py"
    )
