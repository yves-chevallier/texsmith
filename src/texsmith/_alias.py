"""Register legacy extension module aliases for backwards compatibility."""

from __future__ import annotations

import importlib
import sys
import types


_EXTENSION_ALIAS_MODULES: dict[str, tuple[str, dict[str, str] | None]] = {
    "smallcaps": ("texsmith.extensions.smallcaps", None),
    "mermaid": ("texsmith.extensions.mermaid", None),
    "multi_citations": ("texsmith.extensions.multi_citations", None),
    "latex_raw": ("texsmith.extensions.latex_raw", None),
    "latex_text": ("texsmith.extensions.latex_text", None),
    "missing_footnotes": ("texsmith.extensions.missing_footnotes", None),
    "rawlatex": ("texsmith.extensions.latex_raw", {"RawLatexExtension": "LatexRawExtension"}),
}


class _AliasModule(types.ModuleType):
    """Lazy module wrapper that proxies attribute access to the canonical module."""

    __slots__ = ("_alias_map", "_target")

    def __init__(self, name: str, target: str, alias_map: dict[str, str] | None) -> None:
        super().__init__(name)
        self._target = target
        self._alias_map = alias_map or {}
        self.__package__ = name.rpartition(".")[0]

    def _load(self) -> types.ModuleType:
        module = importlib.import_module(self._target)
        if self._alias_map:
            for alias_attr, target_attr in self._alias_map.items():
                setattr(module, alias_attr, getattr(module, target_attr))
            exported = set(getattr(module, "__all__", [])) | set(self._alias_map.keys())
            if exported:
                module.__all__ = sorted(exported)
        sys.modules[self.__name__] = module
        return module

    def __getattr__(self, item: str) -> object:
        module = self._load()
        return getattr(module, item)


def register_aliases() -> None:
    package = sys.modules.get("texsmith")
    if package is None:  # pragma: no cover - defensive
        return
    for alias, (target, attr_map) in _EXTENSION_ALIAS_MODULES.items():
        module_name = f"texsmith.{alias}"
        placeholder = _AliasModule(module_name, target, attr_map)
        sys.modules.setdefault(module_name, placeholder)
        setattr(package, alias, placeholder)


register_aliases()
