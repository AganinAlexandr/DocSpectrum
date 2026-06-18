import csv
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from import_page_near_match_labels_v0 import merge  # noqa: E402


FIELDS = [
    "candidate_id",
    "review_label",
    "review_confidence",
    "reviewer",
    "review_note",
    "reviewed_at",
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class ImportPageNearMatchLabelsTests(unittest.TestCase):
    def test_imports_labels_and_preserves_note_only_rows_without_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.csv"
            canonical_path = root / "canonical.csv"
            summary_path = root / "summary.json"
            write_csv(
                canonical_path,
                [
                    dict.fromkeys(FIELDS, "") | {"candidate_id": "a"},
                    dict.fromkeys(FIELDS, "") | {"candidate_id": "b"},
                ],
            )
            write_csv(
                input_path,
                [
                    {
                        "candidate_id": "a",
                        "review_label": "normative_form",
                        "review_confidence": "high",
                        "reviewer": "human",
                        "review_note": "confirmed",
                        "reviewed_at": "2026-06-18",
                    },
                    {
                        "candidate_id": "b",
                        "review_label": "",
                        "review_confidence": "",
                        "reviewer": "human",
                        "review_note": "looks like prior row",
                        "reviewed_at": "",
                    },
                ],
            )

            summary = merge(input_path, canonical_path, summary_path)

            self.assertEqual(summary["imported_labeled_count"], 1)
            self.assertEqual(summary["pending_with_note_candidate_ids"], ["b"])
            with canonical_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["review_label"], "normative_form")
            self.assertEqual(rows[1]["review_label"], "")
            self.assertEqual(rows[1]["review_note"], "looks like prior row")

    def test_rejects_unknown_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.csv"
            canonical_path = root / "canonical.csv"
            summary_path = root / "summary.json"
            write_csv(
                canonical_path,
                [dict.fromkeys(FIELDS, "") | {"candidate_id": "known"}],
            )
            write_csv(
                input_path,
                [dict.fromkeys(FIELDS, "") | {"candidate_id": "unknown"}],
            )
            with self.assertRaises(ValueError):
                merge(input_path, canonical_path, summary_path)


if __name__ == "__main__":
    unittest.main()
