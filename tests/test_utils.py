import importlib.util
import unittest

from texsmith.utils import escape_latex_chars


LATEXCODEC_AVAILABLE = importlib.util.find_spec("latexcodec") is not None


@unittest.skipUnless(LATEXCODEC_AVAILABLE, "latexcodec not installed")
class EscapeLatexCharsTests(unittest.TestCase):
    def test_unicode_characters_are_encoded(self) -> None:
        payload = "café — 50%"
        escaped = escape_latex_chars(payload)

        self.assertIn("\\'{e}", escaped)
        self.assertIn("\\textemdash", escaped)
        self.assertIn("\\%", escaped)


if __name__ == "__main__":
    unittest.main()
