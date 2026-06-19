import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_non_uuir_all_sections_selection_v0 import (  # noqa: E402
    infer_section_code,
    manifest_candidates,
    object_id_from_number,
    should_exclude_pdf,
    source_number_from_object_id,
)


class NonUuirAllSectionsSelectionTests(unittest.TestCase):
    def test_object_id_from_number(self) -> None:
        self.assertEqual(object_id_from_number("140125"), "1401_25")
        self.assertEqual(source_number_from_object_id("1401_25"), "140125")

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
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\ТЗ Советская 43 электрика.pdf"), "тз"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\2.1 АО г. Люберцы.pdf"), "ао"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\2.2 ДВ г. Люберцы.pdf"), "дв"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\Акт разграничения.pdf"), "акт"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\Письмо №317.pdf"), "письмо"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\3.2 дом АО.pdf"), "ао"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\3.2 дом ДВ.pdf"), "дв"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\3.2 дом ТЗ.pdf"), "тз"),
            (Path(r"E:\MSE_арх\1401_25\Документация на проверку\тех. задание дом.pdf"), "техническое задание"),
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
        self.assertEqual(infer_section_code("4.1.1 СМ_ул Советская, д. 78.pdf"), "СМ")
        self.assertEqual(infer_section_code("Раздел 12 СД - Дмитрия Холодова.pdf"), "СМ")
        self.assertEqual(infer_section_code("Раздел 13_ИД_ТТР.pdf"), "ИД")
        self.assertEqual(infer_section_code("Раздел ИОС5.2.pdf"), "ИНЖЕНЕРИЯ")
        self.assertEqual(infer_section_code("Раздел 5 ЭОМ.pdf"), "ИНЖЕНЕРИЯ")
        self.assertEqual(infer_section_code("Раздел 12 Смета.pdf"), "СМ")
        self.assertEqual(infer_section_code("ул. Советская, д. 78.pdf"), "UNKNOWN")
        self.assertEqual(infer_section_code("АО Советская 43.pdf"), "UNKNOWN")

    def test_manifest_candidates_supports_titled_object_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "non_uuir_titled_objects_v0.csv"
            manifest_path.write_text(
                "object_id,group,gip,org\n1401_25,фундамент,сергеев,ватага\n",
                encoding="utf-8",
            )
            object_dirs = {"1401_25": Path(r"E:\MSE_арх\1401_25 example")}
            rows = manifest_candidates(manifest_path, object_dirs, 1400, 1883)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["object_id"], "1401_25")
            self.assertEqual(rows[0]["source_number"], "140125")
            self.assertEqual(rows[0]["work_group"], "фундамент")
            self.assertEqual(rows[0]["registry_gip"], "сергеев")


if __name__ == "__main__":
    unittest.main()
