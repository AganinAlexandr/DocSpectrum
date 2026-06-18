import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_gip_reconciliation_v0 import (  # noqa: E402
    compare_gip,
    compare_org,
)


class GipReconciliationTests(unittest.TestCase):
    def test_gip_exact_near_and_conflict(self) -> None:
        self.assertEqual(compare_gip("Локтев", "локтев"), "exact_match")
        self.assertEqual(compare_gip("Сергеев", "сергееб"), "ocr_near_match")
        self.assertEqual(compare_gip("Бородин", "локтев"), "source_conflict")

    def test_org_aliases_and_conflict(self) -> None:
        self.assertEqual(
            compare_org("СтройМонтаж", "«Строй Монтаж СП»"),
            "match",
        )
        self.assertEqual(
            compare_org("Стройинвест", "ООО «СП СТРОЙИНВЕСТ ГРУПП»"),
            "match",
        )
        self.assertEqual(
            compare_org("СтройМонтаж", "ООО «ВИТМАР»"),
            "source_conflict",
        )


if __name__ == "__main__":
    unittest.main()
