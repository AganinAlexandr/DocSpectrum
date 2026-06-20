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
        self.assertEqual(object_id_from_number("100124"), "1001_24")
        self.assertEqual(source_number_from_object_id("1401_25"), "140125")
        self.assertEqual(source_number_from_object_id("1001_24"), "100124")

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

    def test_excludes_explanatory_note_pdf(self) -> None:
        samples = [
            Path(r"E:\MSE_арх\1001_24\Раздел 1 ПЗ.pdf"),
            Path(r"E:\MSE_арх\1001_24\Пояснительная записка.pdf"),
            Path(r"E:\MSE_арх\1001_24\Раздел ПД_1 УУХВС05-ПЗ.pdf"),
            Path(r"E:\MSE_арх\1001_24\ПЗ к смете дома.pdf"),
            Path(r"E:\MSE_арх\1001_24\ПЗаписка - дом.pdf"),
        ]
        for path in samples:
            with self.subTest(path=path.name):
                excluded, reason = should_exclude_pdf(path)
                self.assertTrue(excluded)
                self.assertEqual(reason, "пз")

    def test_classifies_and_excludes_tzk_survey(self) -> None:
        path = Path(r"E:\MSE_арх\1001_24\Раздел ТЗК_24-10-2024.pdf")
        self.assertEqual(infer_section_code(path.name), "ТЗК")
        excluded, reason = should_exclude_pdf(path)
        self.assertTrue(excluded)
        self.assertEqual(reason, "тзк")

    def test_classifies_and_excludes_conjuncture_analysis(self) -> None:
        samples = [
            Path(r"E:\MSE_арх\1209_24\КАЦ с приложенными КП.pdf"),
            Path(r"E:\MSE_арх\1269_24\КА Заозерная 23 УУТЭ.pdf"),
            Path(r"E:\MSE_арх\1333_24\КА_подписанный.pdf"),
        ]
        for path in samples:
            with self.subTest(path=path.name):
                self.assertEqual(infer_section_code(path.name), "КАЦ")
                excluded, reason = should_exclude_pdf(path)
                self.assertTrue(excluded)
                self.assertEqual(reason, "кац")

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
            (Path(r"E:\MSE_арх\1001_24\Заключение экспертизы.pdf"), "заключен"),
            (Path(r"E:\MSE_арх\1001_24\Справка ГИП_852153.pdf"), "справка гип"),
            (Path(r"E:\MSE_арх\1001_24\Заявка испр_852719.pdf"), "заявка/исходящее"),
            (Path(r"E:\MSE_арх\1001_24\НОСТРОЙ Иванов.pdf"), "нострой"),
            (Path(r"E:\MSE_арх\1001_24\исх 641 от 27.09.2024.pdf"), "заявка/исходящее"),
            (Path(r"E:\MSE_арх\1001_24\Дог. №2545-К-1.pdf"), "договор"),
            (
                Path(
                    r"E:\MSE_арх\1017_24"
                    r"\2946-К от 15.02.2024 (КЧС, Подольск, ООО ТИВОЛИОН).pdf"
                ),
                "договор кчс",
            ),
            (
                Path(
                    r"E:\MSE_арх\1300_24"
                    r"\2947-К от 15.02.2024 (КЧС, Подольск, ООО СФЕРА).pdf"
                ),
                "договор кчс",
            ),
            (
                Path(
                    r"E:\MSE_арх\1084_24"
                    r"\3155-К от 03.07.2024 "
                    r"(КЧС, ЭЛЕКТРОСТАЛЬ, СМР+ПСД, ООО СТРОЙСЕРВИС)-7.pdf"
                ),
                "договор кчс",
            ),
            (
                Path(r"E:\MSE_арх\1149_24\2947-К от 15.02.2024.pdf"),
                "договор кчс",
            ),
            (
                Path(r"E:\MSE_арх\1280_24\2347ПСД от 26.12.2023.pdf"),
                "договор по front-matter",
            ),
            (
                Path(r"E:\MSE_арх\1214_24\2745-К ДС 3.docx.pdf"),
                "договор по front-matter",
            ),
            (
                Path(r"E:\MSE_арх\1135_24\прил №2 Советская 52к3 гвс.pdf"),
                "приложение к договору",
            ),
            (
                Path(
                    r"E:\MSE_арх\1019_24"
                    r"\2423-К-1 суб от 04.12.2023 (1).pdf"
                ),
                "договор субподряда",
            ),
            (
                Path(
                    r"E:\MSE_арх\1084_24"
                    r"\Шахматка ЦО ул.К.Маркса, 53 (1).pdf"
                ),
                "шахматка отказов",
            ),
            (Path(r"E:\MSE_арх\1001_24\Доп. соглашение 1.pdf"), "допсоглаш"),
            (Path(r"E:\MSE_арх\1001_24\1.1 дом -Т.З.pdf"), "тз"),
            (Path(r"E:\MSE_арх\1001_24\Дефектная_ведомость_(3142-К.pdf"), "дефектная ведомость"),
        ]
        for path, expected_reason in samples:
            with self.subTest(path=path.name):
                excluded, reason = should_exclude_pdf(path)
                self.assertTrue(excluded)
                self.assertEqual(reason, expected_reason)

    def test_keeps_project_cipher_containing_2946(self) -> None:
        excluded, reason = should_exclude_pdf(
            Path(r"E:\MSE_арх\1102_24\ПКР-2946-К-5-ГВС Молодежная 5.pdf")
        )
        self.assertFalse(excluded)
        self.assertEqual(reason, "")

    def test_excludes_residential_building_passports(self) -> None:
        samples = [
            Path(
                r"E:\MSE_арх\1084_24"
                r"\Карла Маркса 53 (технический паспорт МКД).pdf"
            ),
            Path(
                r"E:\MSE_арх\1096_24"
                r"\Карла Маркса 50_08-10-2024_11-49.pdf"
            ),
            Path(r"E:\MSE_арх\1382_25\Паспорт Октябрьская 6.pdf"),
        ]
        for path in samples:
            with self.subTest(path=path.name):
                excluded, reason = should_exclude_pdf(path)
                self.assertTrue(excluded)
                self.assertEqual(reason, "технический паспорт мкд")

    def test_keeps_equipment_passport_name(self) -> None:
        excluded, reason = should_exclude_pdf(
            Path(r"E:\MSE_арх\1001_24\Раздел ОВ паспорт оборудования.pdf")
        )
        self.assertFalse(excluded)
        self.assertEqual(reason, "")

    def test_excludes_filename_only_service_markers(self) -> None:
        samples = [
            Path(r"E:\MSE_арх\1025_24\2. Ответ Минстрой.pdf"),
            Path(r"E:\MSE_арх\1025_24\2296ис от 05.08.2024.pdf"),
            Path(r"E:\MSE_арх\1104_24\Возобновление Парковая 18.pdf"),
            Path(r"E:\MSE_арх\1161_24\24050-Обсл.(Быковского,35).pdf"),
            Path(r"E:\MSE_арх\1071_24\СКподКлюч_Решение5_СменаНазвания.pdf"),
            Path(r"E:\MSE_арх\1099_24\АО5.pdf"),
            Path(r"E:\MSE_арх\1099_24\ДВ5.pdf"),
            Path(r"E:\MSE_арх\1028_24\В ГБУ_Нижегородская 6.pdf"),
            Path(r"E:\MSE_арх\1028_24\Жуковский Нижегородская 6 - 1.2.pdf"),
            Path(
                r"E:\MSE_арх\1071_24"
                r"\г_Красногорск,_ул_Вокзальная_1_ЛС_2_8_БИМ.pdf"
            ),
            Path(r"E:\MSE_арх\1109_24\Стройразвитие проект..pdf"),
        ]
        for path in samples:
            with self.subTest(path=path.name):
                self.assertTrue(should_exclude_pdf(path)[0])

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
        self.assertEqual(infer_section_code("ЛСР по Методике 2020.pdf"), "СМ")
        self.assertEqual(infer_section_code("г. Красногорск, Вокзальная, 1 ЛС.pdf"), "СМ")
        self.assertEqual(infer_section_code("Раздел ПД№5 Система отопления.pdf"), "ОВ")
        self.assertEqual(infer_section_code("Раздел 5 Система электроснабжения.pdf"), "ЭС")
        self.assertEqual(infer_section_code("Раздел №1ПЗ.pdf"), "ПЗ")
        self.assertEqual(infer_section_code("Пояснительная_записка_дом.pdf"), "ПЗ")
        self.assertEqual(infer_section_code("Раздел 3 подписанный титул.pdf"), "АР")
        self.assertEqual(infer_section_code("2.2 Раздел ПД №4 Конструктивные решения.pdf"), "КР")
        self.assertEqual(infer_section_code("Раздел 6. Проект организации капитального ремонта.pdf"), "ПОС")
        self.assertEqual(infer_section_code("Раздел 12 ПД.pdf"), "СМ")
        self.assertEqual(infer_section_code("01-05-04-01-01 ИОСУУ дом.pdf"), "ИНЖЕНЕРИЯ")
        self.assertEqual(infer_section_code("01-05-04-01-01 ХВСУУ дом.pdf"), "ИНЖЕНЕРИЯ")
        self.assertEqual(infer_section_code("Раздел УУГВС дом.pdf"), "ИНЖЕНЕРИЯ")
        self.assertEqual(infer_section_code("ГВС проект Советская 52к3.pdf"), "ИНЖЕНЕРИЯ")
        self.assertEqual(infer_section_code("01-07-01-01-01 ПОКРМолодежная 5.pdf"), "ПОС")
        self.assertEqual(infer_section_code("Раздел №7ПОКР.pdf"), "ПОС")
        self.assertEqual(infer_section_code("18-2726-К-НП9-КР1.pdf"), "КР")
        self.assertEqual(
            infer_section_code("ПКР-2946-К-5-ГВС Молодежная 5.pdf"),
            "ГВС",
        )
        self.assertEqual(
            infer_section_code("ПКР-2946-72-ГВС Молодежная 7к2.pdf"),
            "ГВС",
        )
        self.assertEqual(infer_section_code("Раздел 6 подписанный титул.pdf"), "ПОС")
        self.assertEqual(infer_section_code("Том 5 Раздел 13 Иная документация.pdf"), "ИД")
        self.assertEqual(infer_section_code("1___23_1.PDF"), "ПЗ")
        self.assertEqual(
            infer_section_code("Раздел 7 ПД_898060_23-12-2024_16-56.pdf"),
            "ПОС",
        )
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
