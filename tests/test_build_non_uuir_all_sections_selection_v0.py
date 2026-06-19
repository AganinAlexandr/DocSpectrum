import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_non_uuir_all_sections_selection_v0 import (  # noqa: E402
    infer_section_code,
    object_id_from_number,
    should_exclude_pdf,
)


class NonUuirAllSectionsSelectionTests(unittest.TestCase):
    def test_object_id_from_number(self) -> None:
        self.assertEqual(object_id_from_number("140125"), "1401_25")

    def test_excludes_admin_pdfs(self) -> None:
        excluded, reason = should_exclude_pdf(
            Path(r"E:\MSE_арх\1500_25\Документация на проверку\Выписка СРО.pdf")
        )
        self.assertTrue(excluded)
        self.assertEqual(reason, "выпис")

    def test_keeps_project_pdf(self) -> None:
        excluded, reason = should_exclude_pdf(
            Path(r"E:\MSE_арх\1500_25\Документация на проверку\Раздел №4 КР.pdf")
        )
        self.assertFalse(excluded)
        self.assertEqual(reason, "")

    def test_excludes_nopriz_registry(self) -> None:
        excluded, reason = should_exclude_pdf(
            Path(r"E:\MSE_арх\1676_25\Документация на проверку\НОПРИЗ_Ширяев.pdf")
        )
        self.assertTrue(excluded)
        self.assertEqual(reason, "ноприз")

    def test_excludes_supporting_documents(self) -> None:
        samples = [
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\1.1 ТЗ_ул. Школьная.pdf"), "тз"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\2. Заявление_Школьная.pdf"), "заявлен"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\2.1 АО_ул. Школьная.pdf"), "ао"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\2.2 ДВ_ул. Школьная.pdf"), "дв"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\Допсоглашение №1.pdf"), "допсоглаш"),
        ]
        for path, expected_reason in samples:
            with self.subTest(path=path.name):
                excluded, reason = should_exclude_pdf(path)
                self.assertTrue(excluded)
                self.assertEqual(reason, expected_reason)

    def test_infers_section_code(self) -> None:
        self.assertEqual(infer_section_code("Раздел №4 КР.pdf"), "КР")
        self.assertEqual(infer_section_code("Раздел №7 ПОС.pdf"), "ПОС")
        self.assertEqual(infer_section_code("Раздел №7 ПОКР.pdf"), "ПОС")
        self.assertEqual(infer_section_code("Пояснительная записка.pdf"), "ПЗ")


if __name__ == "__main__":
    unittest.main()
