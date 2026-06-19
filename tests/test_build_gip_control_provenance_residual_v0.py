import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_gip_control_provenance_residual_v0 import (  # noqa: E402
    SECTION_IOS541,
    SECTION_SM,
    calibrate_bands,
    classify_page_match,
    summarize_residual_matches,
)


class GipControlProvenanceResidualTests(unittest.TestCase):
    def test_calibrate_bands_uses_minimum_observed_thresholds(self) -> None:
        bands = calibrate_bands(
            [
                {
                    "review_label": "estimate_boilerplate",
                    "section_code": SECTION_SM,
                    "page_near_structural_v0_2": 0.90,
                    "page_text_segment_jaccard_v0_2": 0.60,
                    "page_text_word_shingle_jaccard_v0_2": 0.70,
                },
                {
                    "review_label": "estimate_boilerplate",
                    "section_code": SECTION_SM,
                    "page_near_structural_v0_2": 0.87,
                    "page_text_segment_jaccard_v0_2": 0.52,
                    "page_text_word_shingle_jaccard_v0_2": 0.49,
                },
            ]
        )
        self.assertEqual(bands["estimate_boilerplate"]["section_code"], SECTION_SM)
        self.assertEqual(bands["estimate_boilerplate"]["assessed_pair_count"], 2)
        self.assertEqual(bands["estimate_boilerplate"]["min_page_near_structural_v0_2"], 0.87)
        self.assertEqual(bands["estimate_boilerplate"]["min_page_text_segment_jaccard_v0_2"], 0.52)
        self.assertEqual(bands["estimate_boilerplate"]["min_page_text_word_shingle_jaccard_v0_2"], 0.49)

    def test_classify_page_match_requires_section_and_all_thresholds(self) -> None:
        bands = {
            "estimate_boilerplate": {
                "section_code": SECTION_SM,
                "min_page_near_structural_v0_2": 0.86,
                "min_page_text_segment_jaccard_v0_2": 0.50,
                "min_page_text_word_shingle_jaccard_v0_2": 0.48,
                "rule_kind_v0_3": "calibrated_minimum_band",
            }
        }
        label, rule = classify_page_match(
            {
                "section_code": SECTION_SM,
                "page_near_structural_v0_2": "0.90",
                "page_text_segment_jaccard_v0_2": "0.55",
                "page_text_word_shingle_jaccard_v0_2": "0.60",
            },
            bands,
        )
        self.assertEqual(label, "estimate_boilerplate")
        self.assertEqual(rule, "calibrated_minimum_band")

        label, _ = classify_page_match(
            {
                "section_code": SECTION_IOS541,
                "page_near_structural_v0_2": "0.90",
                "page_text_segment_jaccard_v0_2": "0.55",
                "page_text_word_shingle_jaccard_v0_2": "0.60",
            },
            bands,
        )
        self.assertEqual(label, "")

    def test_summarize_residual_matches_distinguishes_all_excluded(self) -> None:
        empty = summarize_residual_matches([])
        self.assertEqual(empty["provenance_residual_status_v0_3"], "all_excluded")
        self.assertEqual(empty["residual_page_match_count_v0_3"], 0)
        self.assertEqual(empty["residual_page_near_shingle_mean_v0_3"], "")

        measured = summarize_residual_matches(
            [
                {
                    "page_near_structural_v0_2": "0.90",
                    "page_text_word_shingle_jaccard_v0_2": "0.60",
                    "page_text_segment_jaccard_v0_2": "0.55",
                    "page_exact_signature_match_v0_2": "False",
                },
                {
                    "page_near_structural_v0_2": "0.70",
                    "page_text_word_shingle_jaccard_v0_2": "0.20",
                    "page_text_segment_jaccard_v0_2": "0.25",
                    "page_exact_signature_match_v0_2": "True",
                },
            ]
        )
        self.assertEqual(measured["provenance_residual_status_v0_3"], "measured")
        self.assertEqual(measured["residual_page_match_count_v0_3"], 2)
        self.assertEqual(measured["residual_page_near_exact_share_v0_3"], 0.5)


if __name__ == "__main__":
    unittest.main()
