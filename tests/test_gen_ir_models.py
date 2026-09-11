"""The model generator: drift check, determinism, loud failures."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "gen_ir_models.py"
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "tmark-ir"
SCHEMA = FIXTURES / "ir.json"
VERSION = (FIXTURES / "VERSION").read_text(encoding="utf-8").strip()
COMMITTED = PROJECT_ROOT / "src" / "texsmith" / "ir" / "model.py"


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_ir_models", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve string annotations there
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    return load_generator()


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def run(*args: str, output: Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), "--schema", str(SCHEMA), "--version", VERSION, *args]
    if output is not None:
        cmd += ["--output", str(output)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=PROJECT_ROOT)


def test_check_passes_on_the_committed_file() -> None:
    result = run("--check")
    assert result.returncode == 0, result.stderr


def test_check_fails_when_the_file_drifted(tmp_path: Path) -> None:
    stale = tmp_path / "model.py"
    stale.write_text(COMMITTED.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    result = run("--check", output=stale)
    assert result.returncode == 1
    assert "out of date" in result.stderr


def test_generation_is_deterministic_and_matches_the_committed_file(
    gen: ModuleType, schema: dict, tmp_path: Path
) -> None:
    first = gen.generate(schema, VERSION)
    second = gen.generate(json.loads(json.dumps(schema)), VERSION)
    assert first == second
    assert first == COMMITTED.read_text(encoding="utf-8")
    result = run(output=tmp_path / "model.py")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "model.py").read_text(encoding="utf-8") == first


def test_schema_hash_agrees_with_the_codec(gen: ModuleType, schema: dict) -> None:
    from texsmith.ir import codec, model

    assert gen.canonical_hash(schema) == codec.canonical_hash(schema) == model.SCHEMA_HASH
    # Formatting of the schema file does not change the hash.
    assert gen.canonical_hash(json.loads(json.dumps(schema, indent=4))) == model.SCHEMA_HASH


def test_header_names_version_and_hash() -> None:
    head = COMMITTED.read_text(encoding="utf-8").splitlines()[:3]
    assert head[1] == f"tmark version: {VERSION}"
    assert head[2].startswith("schema sha256: ")


def test_unknown_constructs_fail_loudly(gen: ModuleType, schema: dict) -> None:
    anonymous_object = copy.deepcopy(schema)
    anonymous_object["definitions"]["Author"]["properties"]["home"] = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
    }
    with pytest.raises(gen.SchemaError, match="anonymous object"):
        gen.generate(anonymous_object, VERSION)

    anonymous_enum = copy.deepcopy(schema)
    anonymous_enum["definitions"]["Author"]["properties"]["role"] = {
        "type": "string",
        "enum": ["editor", "author"],
    }
    with pytest.raises(gen.SchemaError, match="anonymous enum"):
        gen.generate(anonymous_enum, VERSION)

    odd_union = copy.deepcopy(schema)
    odd_union["definitions"]["Author"]["properties"]["contact"] = {
        "anyOf": [{"type": "string"}, {"type": "integer"}]
    }
    with pytest.raises(gen.SchemaError, match="anyOf"):
        gen.generate(odd_union, VERSION)

    untyped_required = copy.deepcopy(schema)
    untyped_required["definitions"]["Mystery"] = {"type": "array"}
    with pytest.raises(gen.SchemaError, match="unsupported construct"):
        gen.generate(untyped_required, VERSION)


def test_name_clashes_and_stale_overrides_fail(
    gen: ModuleType, schema: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    clashing = copy.deepcopy(schema)
    clashing["definitions"]["Target"]["oneOf"].append(
        {
            "type": "object",
            "required": ["type", "value"],
            "properties": {
                "type": {"type": "string", "enum": ["Span"]},
                "value": {"type": "string"},
            },
        }
    )
    with pytest.raises(gen.SchemaError, match="clashes"):
        gen.generate(clashing, VERSION)

    monkeypatch.setitem(gen.DEFAULTS, ("Cell", "gone"), 1)
    with pytest.raises(gen.SchemaError, match="no longer match"):
        gen.generate(schema, VERSION)


def test_double_option_must_be_declared(gen: ModuleType, schema: dict) -> None:
    undeclared = copy.deepcopy(schema)
    undeclared["definitions"]["Keys"]["properties"]["subtitle"]["description"] = (
        "`None` when absent, `Some(None)` for `subtitle: null`."
    )
    with pytest.raises(gen.SchemaError, match="DOUBLE_OPTIONS"):
        gen.generate(undeclared, VERSION)
