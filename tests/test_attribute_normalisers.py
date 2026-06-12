"""Tests for custom attribute normaliser resolution (built-in, dotted-path, registry)."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

for entry in (PROJECT_ROOT, SRC_ROOT):
    str_entry = str(entry)
    if str_entry not in sys.path:
        sys.path.insert(0, str_entry)

manifest = __import__("texsmith.core.templates.manifest", fromlist=["x"])
TemplateError = manifest.TemplateError
TemplateAttributeSpec = manifest.TemplateAttributeSpec
register_attribute_normaliser = manifest.register_attribute_normaliser
_resolve_attribute_normaliser = manifest._resolve_attribute_normaliser
_import_normaliser_callable = manifest._import_normaliser_callable


# The module installed below tracks how many times it is imported so the
# caching test can assert a single import.
_NORMALISER_MODULE_SOURCE = """
import_count = 0
import_count += 1


def shout(value, spec, fallback):
    return str(value).upper()
"""


@pytest.fixture
def custom_module(tmp_path, monkeypatch):
    """Install an importable module exposing a normaliser callable."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "rules.py").write_text(_NORMALISER_MODULE_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    # Make sure a stale copy from a previous test run is not reused.
    for name in list(sys.modules):
        if name == "pkg" or name.startswith("pkg."):
            del sys.modules[name]
    _import_normaliser_callable.cache_clear()
    yield
    _import_normaliser_callable.cache_clear()


def _spec() -> TemplateAttributeSpec:
    spec = TemplateAttributeSpec(type="any")
    spec.name = "rules"
    return spec


def test_dotted_path_colon_form_is_imported_and_applied(custom_module) -> None:
    func = _resolve_attribute_normaliser("pkg.rules:shout")
    assert func("quiet", _spec(), None) == "QUIET"


def test_dotted_path_dot_form_resolves(custom_module) -> None:
    func = _resolve_attribute_normaliser("pkg.rules.shout")
    assert func("quiet", _spec(), None) == "QUIET"


def test_builtin_name_still_resolves() -> None:
    func = _resolve_attribute_normaliser("orientation")
    assert func("horizontal", _spec(), None) == "landscape"


def test_unknown_bare_name_raises() -> None:
    with pytest.raises(TemplateError, match="Unknown attribute normaliser 'nope'"):
        _resolve_attribute_normaliser("nope")


def test_missing_module_raises_templateerror() -> None:
    with pytest.raises(TemplateError, match="Could not import module"):
        _resolve_attribute_normaliser("texsmith_does_not_exist.mod:func")


def test_missing_attribute_raises_templateerror(custom_module) -> None:
    with pytest.raises(TemplateError, match="no attribute 'missing'"):
        _resolve_attribute_normaliser("pkg.rules:missing")


def test_non_callable_target_raises_templateerror(custom_module) -> None:
    with pytest.raises(TemplateError, match="non-callable"):
        _resolve_attribute_normaliser("pkg.rules:import_count")


def test_resolution_is_cached(custom_module) -> None:
    _resolve_attribute_normaliser("pkg.rules:shout")
    _resolve_attribute_normaliser("pkg.rules:shout")
    info = _import_normaliser_callable.cache_info()
    assert info.misses == 1
    assert info.hits >= 1
    # The module object was imported exactly once.
    assert sys.modules["pkg.rules"].import_count == 1


def test_register_short_name_works() -> None:
    def double(value, spec, fallback):
        return value * 2

    register_attribute_normaliser("double_test", double)
    try:
        func = _resolve_attribute_normaliser("double_test")
        assert func(3, _spec(), None) == 6
    finally:
        manifest._ATTRIBUTE_NORMALISERS.pop("double_test", None)


def test_register_conflicting_builtin_raises() -> None:
    def passthrough(value, spec, fallback):
        return value

    with pytest.raises(TemplateError, match="shadows a built-in"):
        register_attribute_normaliser("orientation", passthrough)


def test_register_override_builtin_allowed() -> None:
    def forced(value, spec, fallback):
        return "forced"

    original = manifest._ATTRIBUTE_NORMALISERS["orientation"]
    try:
        register_attribute_normaliser("orientation", forced, override=True)
        func = _resolve_attribute_normaliser("orientation")
        assert func("portrait", _spec(), None) == "forced"
    finally:
        manifest._ATTRIBUTE_NORMALISERS["orientation"] = original
