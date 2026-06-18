import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_gip_pdf_selection_v0 import (  # noqa: E402
    crc32_file,
    is_target_kr,
    select_analysis_pdf,
    select_authorship_section,
)


class GipPdfSelectionTests(unittest.TestCase):
    def test_target_selector_excludes_iul_and_pokr(self) -> None:
        self.assertTrue(is_target_kr(Path("Раздел ПД №4 X-КР.pdf")))
        self.assertFalse(is_target_kr(Path("ИУЛ КР.pdf")))
        self.assertFalse(is_target_kr(Path("Раздел ПОКР.pdf")))

    def test_selects_pre_expertise_from_multiple_versions(self) -> None:
        paths = [
            Path("03_Ответы") / "X-КР.pdf",
            Path("01_Документация на проверку") / "X-КР.pdf",
        ]
        selected, rule = select_analysis_pdf(paths)
        self.assertIn("Документация на проверку", str(selected))
        self.assertEqual(rule, "pre_expertise_version")

    def test_authorship_priority_kr_then_pokr_then_ar(self) -> None:
        code, path, _rule = select_authorship_section(
            {
                "КР": [],
                "ПОКР": [Path("x-ПОКР.pdf")],
                "ПОС": [],
                "АР": [Path("x-АР.pdf")],
            }
        )
        self.assertEqual(code, "ПОКР")
        self.assertEqual(path.name, "x-ПОКР.pdf")

    def test_crc32_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "x.pdf"
            path.write_bytes(b"docspectrum")
            self.assertEqual(crc32_file(path), crc32_file(path))


if __name__ == "__main__":
    unittest.main()
