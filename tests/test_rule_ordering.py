import pathlib
import sys
import types
from typing import Any

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
        emojize=lambda text, language=None, variant=None: text
    )

from texsmith.core.rules import RenderPhase, RenderRegistry, renders


def _make_handler(name: str, *, priority: int = 0, before: tuple[str, ...] = (), after: tuple[str, ...] = ()):
    @renders("p", phase=RenderPhase.BLOCK, name=name, priority=priority, before=before, after=after)
    def handler(_node: Any, _context: Any) -> None:
        return None

    definition = getattr(handler, "__render_rule__")
    return definition.bind(handler)


def test_rule_order_respects_priority_and_topology():
    registry = RenderRegistry()
    registry.register(_make_handler("third", priority=1))
    registry.register(_make_handler("first", priority=0))
    registry.register(_make_handler("second", priority=1, after=("first",)))

    rules = registry.rules_for_phase(RenderPhase.BLOCK)["p"]
    assert [rule.name for rule in rules] == ["first", "second", "third"]


def test_rule_order_cycle_detection():
    registry = RenderRegistry()
    registry.register(_make_handler("a", priority=0, before=("b",)))
    with pytest.raises(RuntimeError):
        registry.register(_make_handler("b", priority=0, before=("a",)))
