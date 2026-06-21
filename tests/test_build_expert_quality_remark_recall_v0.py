from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_expert_quality_remark_recall_v0 import (  # noqa: E402
    cell_recall,
    normalize_source_section,
    registry_status,
    worklist_from_arena,
)
from build_expert_quality_experiment_c_v0 import COLUMNS  # noqa: E402
from remark_features import classify_depth, classify_remark, feature_row  # noqa: E402


def test_registry_dates_different_mean_remark_even_without_answer() -> None:
    row = {
        COLUMNS["result_1"]: "45600",
        COLUMNS["positive_result"]: "45610",
        COLUMNS["answer_1"]: "",
    }
    assert registry_status(row) == "remark"


def test_registry_equal_dates_and_empty_answer_mean_clean() -> None:
    row = {
        COLUMNS["result_1"]: "45600",
        COLUMNS["positive_result"]: "45600",
        COLUMNS["answer_1"]: "",
    }
    assert registry_status(row) == "clean"


def test_pokr_content_is_canonical_pos() -> None:
    assert normalize_source_section("ПОКР") == "ПОС"


def test_worklist_deduplicates_pair_documents() -> None:
    arena = [
        {
            "organization": "org",
            "work_type": "work",
            "section_code": "ПОС",
            "group_id": "g",
            "arena_class": "holdout_to_ceiling",
            "left_object_id": "a",
            "right_object_id": "b",
            "left_anchor_roles": "holdout",
            "right_anchor_roles": "ceiling_1_a",
        },
        {
            "organization": "org",
            "work_type": "work",
            "section_code": "ПОС",
            "group_id": "g",
            "arena_class": "holdout_to_ceiling",
            "left_object_id": "a",
            "right_object_id": "c",
            "left_anchor_roles": "holdout",
            "right_anchor_roles": "ceiling_1_a",
        },
    ]
    assert len(worklist_from_arena(arena)) == 3


def test_cell_recall_separates_baseline_layer() -> None:
    reviews = [
        {
            "organization": "org", "work_type": "work", "section_code": "ПОС",
            "expert_anchor_role": "ceiling_1_a", "baseline_remark_count": 10,
        },
        {
            "organization": "org", "work_type": "work", "section_code": "ПОС",
            "expert_anchor_role": "holdout", "baseline_remark_count": 0,
        },
    ]
    row = cell_recall(reviews, "baseline_remark_count", "source1_baseline")[0]
    assert row["holdout_recall_vs_ceiling_v0"] == 0.0


def test_remark_features_are_hash_only_and_typed() -> None:
    row = feature_row("На чертеже исправить узел согласно СП 20.13330.")
    assert "remark_hash" in row
    assert row["primary_category_v0"] == "graphics"
    assert row["depth_class_v0"] == "substantial_candidate"
    assert "На чертеже" not in str(row)


def test_simple_remark_depth() -> None:
    categories, _ = classify_remark("Уточнить номер листа.")
    depth, _ = classify_depth("Уточнить номер листа.", categories)
    assert depth == "simple_candidate"
