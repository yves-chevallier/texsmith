from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mkdocs_latex.context import AssetRegistry, DocumentState
from mkdocs_latex.exceptions import AssetMissingError


class AssetRegistryTests(unittest.TestCase):
    def test_register_and_retrieve_asset(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = AssetRegistry(output_root=root)
            artefact = root / "artefact.pdf"
            artefact.write_text("dummy")

            stored_path = registry.register("figure", artefact)
            self.assertTrue(stored_path.is_file())
            self.assertEqual(stored_path, registry.get("figure"))

    def test_missing_asset_raises(self) -> None:
        registry = AssetRegistry(output_root=Path.cwd())
        with self.assertRaises(AssetMissingError):
            registry.get("unknown")


class DocumentStateTests(unittest.TestCase):
    def test_acronym_tracking(self) -> None:
        state = DocumentState()
        key = state.remember_acronym(
            "LASER", "Light Amplification by Stimulated Emission of Radiation"
        )
        self.assertTrue(key)
        self.assertIn("LASER", state.acronym_keys)
        self.assertEqual(state.acronym_keys["LASER"], key)
        self.assertIn(key, state.acronyms)
        term, expanded = state.acronyms[key]
        self.assertEqual(term, "LASER")
        self.assertTrue(expanded.startswith("Light"))

    def test_acronym_conflict_emits_warning(self) -> None:
        state = DocumentState()
        key = state.remember_acronym("HTTP", "Hypertext Transfer Protocol")
        with self.assertWarnsRegex(UserWarning, "Inconsistent acronym definition"):
            duplicate_key = state.remember_acronym("HTTP", "Different")
        self.assertEqual(duplicate_key, key)
        self.assertEqual(
            state.acronyms[key], ("HTTP", "Hypertext Transfer Protocol")
        )

    def test_solution_collection(self) -> None:
        state = DocumentState()
        payload = {"id": 1, "content": "Solution"}
        state.add_solution(payload)
        self.assertEqual(state.solutions, [payload])


if __name__ == "__main__":
    unittest.main()
