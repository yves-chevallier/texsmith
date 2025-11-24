import pathlib
import sys
import types

import pytest


# ruff: noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "texsmith" not in sys.modules:
    import importlib.machinery

    pkg = types.ModuleType("texsmith")
    pkg.__path__ = [str(ROOT / "texsmith")]
    spec = importlib.machinery.ModuleSpec("texsmith", loader=None, is_package=True)
    spec.submodule_search_locations = pkg.__path__  # type: ignore[attr-defined]
    pkg.__spec__ = spec
    sys.modules["texsmith"] = pkg

if "emoji" not in sys.modules:
    sys.modules["emoji"] = types.SimpleNamespace(
        emojize=lambda text, _language=None, _variant=None: text
    )

if "pylatexenc" not in sys.modules:
    latexencode = types.SimpleNamespace(unicode_to_latex=lambda text, **_: text)
    sys.modules["pylatexenc"] = types.SimpleNamespace(latexencode=latexencode)
    sys.modules["pylatexenc.latexencode"] = latexencode

if "pybtex" not in sys.modules:
    pybtex_pkg = types.ModuleType("pybtex")
    database_pkg = types.ModuleType("pybtex.database")
    input_pkg = types.ModuleType("pybtex.database.input")
    bibtex_mod = types.ModuleType("pybtex.database.input.bibtex")
    exceptions_mod = types.ModuleType("pybtex.exceptions")
    bibtex_mod.Parser = object  # type: ignore[attr-defined]
    exceptions_mod.PybtexError = RuntimeError
    database_pkg.BibliographyData = type("BibliographyData", (), {})  # type: ignore[attr-defined]
    database_pkg.Entry = type("Entry", (), {})  # type: ignore[attr-defined]
    database_pkg.Person = type("Person", (), {})  # type: ignore[attr-defined]
    input_pkg.bibtex = bibtex_mod  # type: ignore[attr-defined]
    database_pkg.input = input_pkg  # type: ignore[attr-defined]
    pybtex_pkg.database = database_pkg  # type: ignore[attr-defined]
    sys.modules["pybtex"] = pybtex_pkg
    sys.modules["pybtex.database"] = database_pkg
    sys.modules["pybtex.database.input"] = input_pkg
    sys.modules["pybtex.database.input.bibtex"] = bibtex_mod
    sys.modules["pybtex.exceptions"] = exceptions_mod

from texsmith.core.conversion.renderer import TemplateFragment, TemplateRenderer
from texsmith.core.templates import TemplateError
from texsmith.core.templates.manifest import TemplateSlot
from texsmith.core.templates.runtime import TemplateRuntime


def _runtime_with_slots(
    slots: dict[str, TemplateSlot], default_slot: str = "main"
) -> TemplateRuntime:
    return TemplateRuntime(
        instance=None,  # type: ignore[arg-type] - instance not needed for slot validation
        name="dummy",
        engine=None,
        requires_shell_escape=False,
        slots=slots,
        default_slot=default_slot,
        formatter_overrides={},
        base_level=0,
        extras={},
    )


def test_renderer_rejects_unknown_slot():
    runtime = _runtime_with_slots({"main": TemplateSlot(default=True)})
    renderer = TemplateRenderer(runtime)
    fragment = TemplateFragment(
        stem="doc",
        latex="body",
        default_slot="main",
        slot_outputs={"unknown": "latext"},
        slot_includes=set(),
    )

    with pytest.raises(TemplateError, match="unknown slot"):
        renderer.render([fragment], output_dir=pathlib.Path("build"))
