from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_expert_quality_experiment_c_v0 import (  # noqa: E402
    COLUMNS,
    anchor_for_expert,
    build_groups,
    build_registry_rows,
    classify_section,
    composition_cosine,
    normalize_object_id,
    outcome_flags,
    pair_arena_class,
    set_jaccard,
    should_drop_registry_row,
)


def test_normalize_object_id_handles_registry_numbers() -> None:
    assert normalize_object_id("151525") == "1515_25"
    assert normalize_object_id("29224") == "0292_24"
    assert normalize_object_id("1515_25") == "1515_25"


def test_section_scope_is_kr_and_pos_only() -> None:
    assert classify_section("КР") == "КР"
    assert classify_section("пос") == "ПОС"
    assert classify_section("ПЗ") == ""


def test_anchor_mapping_is_generic() -> None:
    assert anchor_for_expert("Крюкова") == ("ceiling_1_b", "1")
    assert anchor_for_expert("Кузнецов") == ("holdout", "holdout")
    assert anchor_for_expert("Другой") == ("unlabeled", "")


def test_registry_filters_refusal_signature_and_placeholder() -> None:
    refusal = {COLUMNS["expert_action"]: "отказ_эксперта"}
    signature = {COLUMNS["expert_action"]: "подп"}
    placeholder = {COLUMNS["received_remarks"]: "43831"}

    assert should_drop_registry_row(refusal) == "expert_refusal"
    assert should_drop_registry_row(signature) == "signature_only"
    assert should_drop_registry_row(placeholder) == "placeholder_date"


def test_outcome_uses_answer_not_received_remarks_as_signal() -> None:
    row = {
        COLUMNS["received_remarks"]: "45000",
        COLUMNS["result_1"]: "45010",
        COLUMNS["positive_result"]: "45010",
        COLUMNS["answer_1"]: "",
    }
    assert outcome_flags(row) == (True, False)
    row[COLUMNS["answer_1"]] = "Ответ на замечание"
    assert outcome_flags(row) == (False, True)


def test_candidate_and_gold_groups_require_distinct_experts_with_remarks() -> None:
    raw_rows = [
        {
            COLUMNS["object_number"]: "100124",
            COLUMNS["organization"]: "Орг",
            COLUMNS["work_type"]: "фундамент",
            COLUMNS["section"]: "КР",
            COLUMNS["expert_name"]: "Крюкова",
            COLUMNS["answer_1"]: "ответ",
        },
        {
            COLUMNS["object_number"]: "100224",
            COLUMNS["organization"]: "Орг",
            COLUMNS["work_type"]: "фундамент",
            COLUMNS["section"]: "КР",
            COLUMNS["expert_name"]: "Кузнецов",
            COLUMNS["answer_1"]: "ответ",
        },
    ]
    registry_rows, drops = build_registry_rows(raw_rows)
    group_rows, candidates = build_groups(registry_rows)

    assert not drops
    assert len(candidates) == 1
    assert group_rows[0]["gold_status"] == "gold"


def test_similarity_primitives() -> None:
    left = {
        "text_count": 0.5,
        "line_count": 0.5,
    }
    right = {
        "text_count": 0.5,
        "line_count": 0.5,
    }
    assert abs(composition_cosine(left, right) - 1.0) < 1e-12
    assert set_jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_arena_classification_prioritizes_holdout_pairs() -> None:
    assert pair_arena_class({"holdout"}, {"ceiling_1_a"}) == "holdout_to_ceiling"
    assert pair_arena_class({"holdout"}, {"floor_3"}) == "holdout_to_floor"
    assert pair_arena_class({"ceiling_1_b"}, {"floor_3"}) == "ceiling_to_floor"
    assert pair_arena_class({"holdout", "ceiling_1_a"}, {"holdout"}) == "other"


def test_invalid_registry_object_number_is_counted_as_drop() -> None:
    rows, drops = build_registry_rows(
        [{COLUMNS["object_number"]: "1", COLUMNS["section"]: "КР"}]
    )
    assert rows == []
    assert drops["invalid_object_id"] == 1
