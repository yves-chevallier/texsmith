from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from texsmith.core.context import AssetRegistry, DocumentState
from texsmith.core.exceptions import AssetMissingError


def test_register_and_retrieve_asset() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = AssetRegistry(output_root=root)
        artefact = root / "artefact.pdf"
        artefact.write_text("dummy")

        stored_path = registry.register("figure", artefact)
        assert stored_path.is_file()
        assert stored_path == registry.get("figure")


def test_missing_asset_raises() -> None:
    registry = AssetRegistry(output_root=Path.cwd())
    with pytest.raises(AssetMissingError):
        registry.get("unknown")


def test_acronym_tracking() -> None:
    state = DocumentState()
    key = state.remember_acronym("LASER", "Light Amplification by Stimulated Emission of Radiation")
    assert key
    assert "LASER" in state.acronym_keys
    assert state.acronym_keys["LASER"] == key
    assert key in state.acronyms
    term, expanded = state.acronyms[key]
    assert term == "LASER"
    assert expanded.startswith("Light")


def test_acronym_conflict_emits_warning() -> None:
    state = DocumentState()
    key = state.remember_acronym("HTTP", "Hypertext Transfer Protocol")
    with pytest.warns(UserWarning, match="Inconsistent acronym definition"):
        duplicate_key = state.remember_acronym("HTTP", "Different")
    assert duplicate_key == key
    assert state.acronyms[key] == ("HTTP", "Hypertext Transfer Protocol")


def test_solution_collection() -> None:
    state = DocumentState()
    payload = {"id": 1, "content": "Solution"}
    state.add_solution(payload)
    assert state.solutions == [payload]
