import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from text_features import normalize_text  # noqa: E402


class NormalizeTextTests(unittest.TestCase):
    def test_repairs_known_cyrillic_corruption(self) -> None:
        value = "ПÐОЕКТНАЯ Ðеконструкöиþ"
        self.assertEqual(normalize_text(value), "проектная реконструкцию")

    def test_repairs_already_lowercased_export_text(self) -> None:
        value = "ðаздел проектной документаöии с применениþ"
        self.assertEqual(normalize_text(value), "раздел проектной документации с применению")

    def test_keeps_existing_normalization_rules(self) -> None:
        self.assertEqual(normalize_text("  Ёлка   ЕЩЁ  "), "елка еще")


if __name__ == "__main__":
    unittest.main()
