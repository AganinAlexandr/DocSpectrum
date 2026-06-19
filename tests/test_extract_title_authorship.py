import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from extract_title_authorship_v0 import (  # noqa: E402
    candidate_line_windows,
    group_title_pages,
    organization_candidates,
    person_candidates,
)


class ExtractTitleAuthorshipTests(unittest.TestCase):
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
