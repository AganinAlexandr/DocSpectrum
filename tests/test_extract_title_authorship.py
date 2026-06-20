import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from extract_title_authorship_v0 import (  # noqa: E402
    canonical_section_kind,
    extract_declared_section,
    candidate_line_windows,
    group_title_pages,
    organization_candidates,
    person_candidates,
)


class ExtractTitleAuthorshipTests(unittest.TestCase):
    def test_declared_kind_uses_subsection_not_generic_section_five(self) -> None:
        rows = [
            {
                "page_number": 1,
                "y": 10,
                "text": "ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ",
            },
            {
                "page_number": 1,
                "y": 20,
                "text": "Раздел 5 Сведения об инженерном оборудовании, о сетях",
            },
            {
                "page_number": 1,
                "y": 30,
                "text": "Подраздел 5.1 «Система электроснабжения»",
            },
        ]

        result = extract_declared_section(rows)

        self.assertEqual(result["declared_section_number"], "5")
        self.assertEqual(result["declared_subsection_number"], "5.1")
        self.assertEqual(result["declared_section_kind"], "ЭС")
        self.assertIn("Сведения об инженерном оборудовании", result["declared_section_text"])
        self.assertIn("Система электроснабжения", result["declared_subsection_text"])

    def test_generic_section_five_without_subsection_is_not_classified(self) -> None:
        result = extract_declared_section(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": "ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ",
                },
                {
                    "page_number": 1,
                    "y": 20,
                    "text": "Раздел 5 Сведения об инженерном оборудовании, о сетях",
                },
            ]
        )

        self.assertEqual(result["declared_section_kind"], "")
        self.assertEqual(result["declared_section_status"], "section_text_only")

    def test_integer_subsection_number_and_multiline_ov_title(self) -> None:
        result = extract_declared_section(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": "ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ",
                },
                {
                    "page_number": 1,
                    "y": 20,
                    "text": (
                        "Раздел 5. Сведения об инженерном оборудовании, "
                        "о сетях инженерно-технического обеспечения"
                    ),
                },
                {
                    "page_number": 1,
                    "y": 30,
                    "text": (
                        "Подраздел 4. Отопление, вентиляция и "
                        "кондиционирование воздуха,"
                    ),
                },
                {
                    "page_number": 1,
                    "y": 40,
                    "text": "тепловые сети.",
                },
                {
                    "page_number": 1,
                    "y": 50,
                    "text": "Шифр 123-ОВ",
                },
            ]
        )

        self.assertEqual(result["declared_subsection_number"], "4")
        self.assertEqual(result["declared_section_kind"], "ОВ")
        self.assertIn("тепловые сети", result["declared_subsection_text"])
        self.assertNotIn("Шифр", result["declared_subsection_text"])

    def test_ignores_organization_word_subdivision(self) -> None:
        result = extract_declared_section(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": "ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ",
                },
                {
                    "page_number": 1,
                    "y": 20,
                    "text": "Раздел 5. Сведения об инженерном оборудовании",
                },
                {
                    "page_number": 1,
                    "y": 30,
                    "text": "Обособленное подразделение фактический адрес",
                },
            ]
        )

        self.assertEqual(result["declared_subsection_number"], "")
        self.assertEqual(result["declared_section_kind"], "")
        self.assertEqual(result["declared_section_status"], "section_text_only")

    def test_distinguishes_water_and_combined_water_sewerage(self) -> None:
        self.assertEqual(
            canonical_section_kind("Подраздел 2. Система водоснабжения"),
            "ВС",
        )
        self.assertEqual(
            canonical_section_kind(
                "Подраздел 2. Система водоснабжения и водоотведения"
            ),
            "ВК",
        )

    def test_classifies_non_engineering_section_from_title(self) -> None:
        result = extract_declared_section(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": "ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ",
                },
                {
                    "page_number": 1,
                    "y": 20,
                    "text": "Раздел 7. Проект организации строительства",
                },
            ]
        )

        self.assertEqual(result["declared_section_number"], "7")
        self.assertEqual(result["declared_section_kind"], "ПОС")
        self.assertEqual(result["declared_section_match_status"], "resolved")

    def test_title_name_can_override_nonstandard_section_number(self) -> None:
        result = extract_declared_section(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": "ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ",
                },
                {
                    "page_number": 1,
                    "y": 20,
                    "text": "Раздел 6. Проект организации капитального ремонта",
                },
            ]
        )

        self.assertEqual(result["declared_section_number"], "6")
        self.assertEqual(result["declared_section_kind"], "ПОС")
        self.assertEqual(
            result["declared_section_match_name"],
            "Проект организации строительства",
        )

    def test_groups_title_pages_by_lead_and_executor_rule(self) -> None:
        self.assertEqual(group_title_pages([1, 2]), [[1, 2]])
        self.assertEqual(group_title_pages([1, 2, 3]), [[1, 2], [3]])
        self.assertEqual(group_title_pages([1, 2, 3, 4]), [[1, 2], [3, 4]])
        self.assertEqual(group_title_pages([1, 2, 3, 4, 5]), [[1, 2], [3, 4, 5]])
        self.assertEqual(group_title_pages([]), [])

    def test_extracts_organization_candidate(self) -> None:
        result = organization_candidates(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": "АО «Проектировщик»",
                    "normalized": "ао «проектировщик»",
                }
            ]
        )
        self.assertEqual(result[0]["organization_name_raw"], "АО «Проектировщик»")

    def test_extracts_person_near_gip(self) -> None:
        result = person_candidates(
            [
                {
                    "page_number": 2,
                    "y": 100,
                    "text": "ГИП",
                    "normalized": "гип",
                },
                {
                    "page_number": 2,
                    "y": 120,
                    "text": "Траскунова Е.М.",
                    "normalized": "траскунова е.м.",
                },
            ]
        )
        self.assertEqual(result[0]["gip_surname_normalized"], "траскунова")

    def test_joins_split_organization_name(self) -> None:
        lines = [
            {
                "page_number": 1,
                "y": 10,
                "text": "Общество с ограниченной",
                "normalized": "общество с ограниченной",
            },
            {
                "page_number": 1,
                "y": 30,
                "text": "ответственностью",
                "normalized": "ответственностью",
            },
            {
                "page_number": 1,
                "y": 50,
                "text": '"Строй Монтаж СП"',
                "normalized": '"строй монтаж сп"',
            },
        ]
        windows = candidate_line_windows(lines)
        self.assertIn(
            'Общество с ограниченной ответственностью "Строй Монтаж СП"',
            [item["text"] for item in windows],
        )
        result = organization_candidates(lines)
        self.assertIn(
            "строй монтаж сп",
            result[0]["organization_name_normalized"],
        )

    def test_accepts_common_ocr_marker_errors(self) -> None:
        organizations = organization_candidates(
            [
                {
                    "page_number": 1,
                    "y": 10,
                    "text": '000 «СП СТРОЙИНВЕСТ ГРУПП»',
                    "normalized": '000 «сп стройинвест групп»',
                }
            ]
        )
        people = person_candidates(
            [
                {
                    "page_number": 2,
                    "y": 100,
                    "text": "Тлавный инженер проекта Локтев А.Н.",
                    "normalized": "тлавный инженер проекта локтев а.н.",
                }
            ]
        )
        self.assertIn("стройинвест", organizations[0]["organization_name_normalized"])
        self.assertEqual(people[0]["gip_surname_normalized"], "локтев")

    def test_extracts_initials_before_surname(self) -> None:
        people = person_candidates(
            [
                {
                    "page_number": 2,
                    "y": 100,
                    "text": "Главный инженер проекта В.В. Ефимов",
                    "normalized": "главный инженер проекта в.в. ефимов",
                }
            ]
        )
        self.assertEqual(people[0]["gip_surname_normalized"], "ефимов")
        self.assertEqual(people[0]["gip_initials"], "ВВ")


if __name__ == "__main__":
    unittest.main()
