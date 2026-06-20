import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_title_authorship_range_v0 import (  # noqa: E402
    section_code,
    select_version,
)


class TitleAuthorshipRangeTests(unittest.TestCase):
    def test_section_code_accepts_comma_boundary_and_maps_pokr_to_pos(self) -> None:
        self.assertEqual(section_code(Path("Раздел 4,КР.pdf")), "КР")
        self.assertEqual(section_code(Path("Раздел 7-ПОС.pdf")), "ПОС")
        self.assertEqual(section_code(Path("Раздел 7-ПОКР.pdf")), "ПОС")
        self.assertIsNone(section_code(Path("ИУЛ к Разделу 4 - КР.pdf")))

    def test_section_code_supports_fallback_project_sections_but_not_pz(self) -> None:
        self.assertEqual(section_code(Path("ИОС5.1 дом.pdf")), "ИНЖЕНЕРИЯ")
        self.assertEqual(
            section_code(Path("Раздел 5 Система электроснабжения.pdf")),
            "ИНЖЕНЕРИЯ",
        )
        self.assertEqual(section_code(Path("Раздел 4 ПД.pdf")), "КР")
        self.assertEqual(section_code(Path("Раздел 7 ПД.pdf")), "ПОС")
        self.assertEqual(section_code(Path("Раздел 12 ПД.pdf")), "СМ")
        self.assertIsNone(section_code(Path("Пояснительная записка ПЗ.pdf")))
        self.assertIsNone(section_code(Path("Раздел №1 ПЗ 13.ПР-2024.КР.pdf")))
        self.assertIsNone(section_code(Path("ИУЛ Раздел 4.pdf")))

    def test_selects_single_duplicate_and_any_version_for_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.pdf"
            duplicate = root / "duplicate.pdf"
            other = root / "other.pdf"
            first.write_bytes(b"same")
            duplicate.write_bytes(b"same")
            other.write_bytes(b"other")
            selected, rule = select_version([first, duplicate])
            self.assertEqual(selected, duplicate if duplicate < first else first)
            self.assertEqual(rule, "duplicate_identical_content")
            selected, rule = select_version([first, other])
            self.assertEqual(selected, first)
            self.assertEqual(rule, "any_version_for_gip_identity")


if __name__ == "__main__":
    unittest.main()
