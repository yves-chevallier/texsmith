import pathlib
import sys
import types

# ruff: noqa: E402
import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "texsmith" not in sys.modules:
    pkg = types.ModuleType("texsmith")
    pkg.__path__ = [str(ROOT / "texsmith")]
    spec = types.SimpleNamespace()
    try:
        import importlib.machinery

        spec = importlib.machinery.ModuleSpec("texsmith", loader=None, is_package=True)
        spec.submodule_search_locations = pkg.__path__
    except Exception:  # pragma: no cover - defensive
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

if "mkdocs" not in sys.modules:
    mkdocs_mod = types.ModuleType("mkdocs")
    plugins_mod = types.ModuleType("mkdocs.plugins")
    config_mod = types.ModuleType("mkdocs.config")
    config_options_mod = types.ModuleType("mkdocs.config.config_options")
    config_options_mod.Type = lambda *_, **__: None  # type: ignore[assignment]
    config_mod.config_options = config_options_mod  # type: ignore[attr-defined]
    defaults_mod = types.ModuleType("mkdocs.config.defaults")
    defaults_mod.MkDocsConfig = type("MkDocsConfig", (), {})  # minimal placeholder
    structure_mod = types.ModuleType("mkdocs.structure")
    files_mod = types.ModuleType("mkdocs.structure.files")
    files_mod.Files = type("Files", (), {})  # minimal placeholder
    pages_mod = types.ModuleType("mkdocs.structure.pages")
    pages_mod.Page = type("Page", (), {})  # minimal placeholder
    plugins_mod.BasePlugin = type("BasePlugin", (), {})  # minimal placeholder
    plugins_mod.event_priority = lambda *_args, **_kwargs: (lambda fn: fn)
    mkdocs_mod.plugins = plugins_mod  # type: ignore[attr-defined]
    mkdocs_mod.config = config_mod  # type: ignore[attr-defined]
    mkdocs_mod.structure = structure_mod  # type: ignore[attr-defined]
    sys.modules["mkdocs"] = mkdocs_mod
    sys.modules["mkdocs.plugins"] = plugins_mod
    sys.modules["mkdocs.config"] = config_mod
    sys.modules["mkdocs.config.config_options"] = config_options_mod
    sys.modules["mkdocs.config.defaults"] = defaults_mod
    sys.modules["mkdocs.structure"] = structure_mod
    sys.modules["mkdocs.structure.files"] = files_mod
    sys.modules["mkdocs.structure.pages"] = pages_mod

if "markdown" not in sys.modules:
    markdown_mod = types.ModuleType("markdown")
    extensions_mod = types.ModuleType("markdown.extensions")
    inlinepatterns_mod = types.ModuleType("markdown.inlinepatterns")
    treeprocessors_mod = types.ModuleType("markdown.treeprocessors")
    preprocessors_mod = types.ModuleType("markdown.preprocessors")
    extensions_mod.Extension = type("Extension", (), {})  # minimal placeholder
    inlinepatterns_mod.InlineProcessor = type("InlineProcessor", (), {})  # minimal placeholder
    treeprocessors_mod.Treeprocessor = type("Treeprocessor", (), {})  # minimal placeholder
    preprocessors_mod.Preprocessor = type("Preprocessor", (), {})  # minimal placeholder
    markdown_mod.Markdown = type("Markdown", (), {})  # minimal placeholder
    markdown_mod.extensions = extensions_mod  # type: ignore[attr-defined]
    sys.modules["markdown"] = markdown_mod
    sys.modules["markdown.extensions"] = extensions_mod
    sys.modules["markdown.inlinepatterns"] = inlinepatterns_mod
    sys.modules["markdown.treeprocessors"] = treeprocessors_mod
    sys.modules["markdown.preprocessors"] = preprocessors_mod

if "pybtex" not in sys.modules:
    pybtex_pkg = types.ModuleType("pybtex")
    database_pkg = types.ModuleType("pybtex.database")
    input_pkg = types.ModuleType("pybtex.database.input")
    bibtex_mod = types.ModuleType("pybtex.database.input.bibtex")
    exceptions_mod = types.ModuleType("pybtex.exceptions")
    BibliographyData = type("BibliographyData", (), {})  # minimal placeholders
    Entry = type("Entry", (), {})
    Person = type("Person", (), {})
    bibtex_mod.Parser = object  # type: ignore[attr-defined]
    exceptions_mod.PybtexError = RuntimeError
    database_pkg.BibliographyData = BibliographyData  # type: ignore[attr-defined]
    database_pkg.Entry = Entry  # type: ignore[attr-defined]
    database_pkg.Person = Person  # type: ignore[attr-defined]
    input_pkg.bibtex = bibtex_mod  # type: ignore[attr-defined]
    database_pkg.input = input_pkg  # type: ignore[attr-defined]
    pybtex_pkg.database = database_pkg  # type: ignore[attr-defined]
    sys.modules["pybtex"] = pybtex_pkg
    sys.modules["pybtex.database"] = database_pkg
    sys.modules["pybtex.database.input"] = input_pkg
    sys.modules["pybtex.database.input.bibtex"] = bibtex_mod
    sys.modules["pybtex.exceptions"] = exceptions_mod

from texsmith.adapters.latex import renderer as renderer_mod
from texsmith.adapters.latex.renderer import LaTeXRenderer


def test_entry_point_factory_receives_renderer():
    calls: list[LaTeXRenderer] = []

    def plugin(renderer: LaTeXRenderer) -> None:
        calls.append(renderer)

    renderer = LaTeXRenderer(copy_assets=False, convert_assets=False, hash_assets=False)
    renderer._apply_entry_point(plugin)

    assert calls == [renderer]


def test_entry_point_register_error_surfaces():
    class BadPlugin:
        def register(self, renderer: LaTeXRenderer) -> None:  # pragma: no cover - intentional error
            raise TypeError("boom")

    renderer = LaTeXRenderer(copy_assets=False, convert_assets=False, hash_assets=False)

    with pytest.raises(TypeError):
        renderer._apply_entry_point(BadPlugin())


def test_entry_points_sorted_by_name(monkeypatch):
    LaTeXRenderer._ENTRY_POINT_PAYLOADS = None

    class _EP:
        def __init__(self, name: str, payload: object, priority: int = 0) -> None:
            self.name = name
            self._payload = payload
            self.priority = priority

        def load(self) -> object:
            return self._payload

    class _Group(list):
        def select(self, group: str):
            return self if group == LaTeXRenderer._ENTRY_POINT_GROUP else []

    fake_group = _Group([_EP("zzz", "late"), _EP("aaa", "early"), _EP("mid", "middle", priority=1)])
    monkeypatch.setattr(renderer_mod.metadata, "entry_points", lambda: fake_group)

    payloads = list(LaTeXRenderer._iter_entry_point_payloads())
    assert payloads == ["early", "late", "middle"]
