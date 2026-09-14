from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from texsmith.core.context import AssetRegistry, DocumentState
from texsmith.core.exceptions import AssetMissingError
from texsmith.diagnostics import LoggingEmitter


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
    key = state.remember_abbreviation(
        "LASER", "Light Amplification by Stimulated Emission of Radiation"
    )
    assert key
    assert "LASER" in state.acronym_keys
    assert state.acronym_keys["LASER"] == key
    assert key in state.acronyms
    term, expanded = state.acronyms[key]
    assert term == "LASER"
    assert expanded.startswith("Light")


def test_acronym_conflict_emits_diagnostic() -> None:
    state = DocumentState()
    emitter = LoggingEmitter()
    key = state.remember_abbreviation("HTTP", "Hypertext Transfer Protocol", emitter=emitter)
    duplicate_key = state.remember_abbreviation("HTTP", "Different", emitter=emitter)
    assert duplicate_key == key
    assert state.acronyms[key] == ("HTTP", "Hypertext Transfer Protocol")
    (recorded,) = emitter.sink
    assert recorded.code == "metadata-invalid"
    assert "Inconsistent acronym definition" in recorded.message


def test_acronym_conflict_stays_quiet_without_an_emitter() -> None:
    """No emitter reachable (the default): silent, not a crash."""
    state = DocumentState()
    key = state.remember_abbreviation("HTTP", "Hypertext Transfer Protocol")
    duplicate_key = state.remember_abbreviation("HTTP", "Different")
    assert duplicate_key == key
