import csv
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_page_near_match_review_sheet_v0 import build  # noqa: E402


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class PageNearMatchReviewSheetTests(unittest.TestCase):
    def test_build_preserves_review_and_exposes_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = root / "queue.csv"
            export_root = root / "exports"
            output = root / "review.csv"
            base = {
                "review_rank": "1",
                "review_label": "",
                "review_confidence": "",
                "reviewer": "",
                "review_note": "",
                "reviewed_at": "",
                "candidate_id": "candidate-1",
                "candidate_strength": "rare_text_high_overlap",
                "left_object_id": "left",
                "left_crc32": "aaaaaaaa",
                "left_page_number": "2",
                "left_cohort": "A",
                "left_file_name": "left.pdf",
                "left_pdf_path": "left.pdf",
                "right_object_id": "right",
                "right_crc32": "bbbbbbbb",
                "right_page_number": "3",
                "right_cohort": "B",
                "right_file_name": "right.pdf",
                "right_pdf_path": "right.pdf",
                "left_section_code": "S",
                "near_match_similarity_v0": "0.9",
                "text_segment_jaccard": "0.5",
                "shared_text_segment_count": "1",
                "rare_shared_text_segment_count": "1",
                "shared_table_layout_count": "0",
                "shared_table_content_count": "0",
            }
            write_csv(queue, [base])
            for object_id, crc32, page, unique in (
                ("left", "aaaaaaaa", "2", "left unique"),
                ("right", "bbbbbbbb", "3", "right unique"),
            ):
                write_csv(
                    export_root / object_id / f"doc_{crc32}" / "text_segments.csv",
                    [
                        {
                            "page_number": page,
                            "text_value": "Shared text",
                            "x1": "1",
                            "y1": "1",
                            "text_segment_id": "1",
                        },
                        {
                            "page_number": page,
                            "text_value": unique,
                            "x1": "1",
                            "y1": "2",
                            "text_segment_id": "2",
                        },
                    ],
                )
            write_csv(
                output,
                [
                    {
                        "candidate_id": "candidate-1",
                        "review_label": "normative_form",
                        "review_confidence": "high",
                        "reviewer": "human",
                        "review_note": "kept",
                        "reviewed_at": "2026-06-18",
                    }
                ],
            )

            build(queue, export_root, output, 30)
            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))

            self.assertEqual(row["review_label"], "normative_form")
            self.assertEqual(row["review_note"], "kept")
            self.assertEqual(row["shared_text_excerpt"], "Shared text")
            self.assertEqual(row["left_only_text_excerpt"], "left unique")
            self.assertEqual(row["right_only_text_excerpt"], "right unique")


if __name__ == "__main__":
    unittest.main()
