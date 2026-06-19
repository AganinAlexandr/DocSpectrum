from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_gip_control_near_match_v0 import (  # noqa: E402
    choose_better,
    summarize_matches,
)


def test_choose_better_prefers_shingle_when_structural_ties() -> None:
    candidate = {
        "page_near_structural_v0_2": 0.9,
        "page_text_word_shingle_jaccard_v0_2": 0.2,
        "page_text_segment_jaccard_v0_2": 0.1,
        "page_exact_signature_match_v0_2": False,
    }
    contender = {
        "page_near_structural_v0_2": 0.9,
        "page_text_word_shingle_jaccard_v0_2": 0.3,
        "page_text_segment_jaccard_v0_2": 0.05,
        "page_exact_signature_match_v0_2": False,
    }

    best = choose_better(candidate, contender)

    assert best is contender


def test_summarize_matches_reports_bidirectional_means() -> None:
    matches_lr = [
        {
            "page_near_structural_v0_2": 0.8,
            "page_text_word_shingle_jaccard_v0_2": 0.2,
            "page_text_segment_jaccard_v0_2": 0.1,
            "page_table_layout_jaccard_v0_2": 0.5,
            "page_table_content_jaccard_v0_2": 0.0,
            "page_exact_signature_match_v0_2": False,
        }
    ]
    matches_rl = [
        {
            "page_near_structural_v0_2": 1.0,
            "page_text_word_shingle_jaccard_v0_2": 0.4,
            "page_text_segment_jaccard_v0_2": 0.2,
            "page_table_layout_jaccard_v0_2": 1.0,
            "page_table_content_jaccard_v0_2": 1.0,
            "page_exact_signature_match_v0_2": True,
        }
    ]

    summary = summarize_matches(matches_lr, matches_rl)

    assert summary["page_near_similarity_mean_v0_2"] == 0.9
    assert summary["page_near_similarity_median_v0_2"] == 0.9
    assert summary["page_near_shingle_mean_v0_2"] == 0.3
    assert summary["page_near_exact_share_v0_2"] == 0.5
    assert summary["page_bidirectional_match_count_v0_2"] == 2
