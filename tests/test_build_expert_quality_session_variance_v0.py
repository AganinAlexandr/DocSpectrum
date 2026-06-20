from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_expert_quality_session_variance_v0 import (  # noqa: E402
    build_session_rows,
    merge_object_section_rows,
    quantile,
    summarize_experts,
)


def source_row(
    object_id: str,
    section: str,
    clean: bool,
    remark: bool,
    date: str = "2025-02-13",
) -> dict[str, str]:
    return {
        "object_id": object_id,
        "organization": "АО ССУ № 3",
        "work_type": "фундамент",
        "section_code": section,
        "expert_hash": "holdout-hash",
        "expert_anchor_role": "holdout",
        "expert_quality_class": "holdout",
        "session_start_date": date,
        "has_first_round_remark": str(remark),
        "clean_first_round_pass": str(clean),
    }


def test_kr_and_pos_same_date_are_one_session() -> None:
    records = merge_object_section_rows(
        [
            source_row("1483_25", "КР", True, False),
            source_row("1483_25", "ПОС", True, False),
            source_row("1484_25", "КР", True, False),
            source_row("1484_25", "ПОС", True, False),
        ]
    )
    sessions = build_session_rows(records)

    assert len(sessions) == 1
    assert sessions[0]["object_count"] == 2
    assert sessions[0]["section_count"] == 4
    assert sessions[0]["section_codes"] == "КР|ПОС"
    assert sessions[0]["clean_share_all_sections"] == 1.0


def test_different_dates_are_independent_sessions() -> None:
    records = merge_object_section_rows(
        [
            source_row("1483_25", "КР", True, False, "2025-02-13"),
            source_row("1630_25", "КР", True, False, "2025-03-20"),
        ]
    )
    assert len(build_session_rows(records)) == 2


def test_duplicate_registry_lines_do_not_create_extra_sections() -> None:
    records = merge_object_section_rows(
        [
            source_row("1483_25", "КР", False, True),
            source_row("1483_25", "КР", False, True),
        ]
    )
    sessions = build_session_rows(records)

    assert len(records) == 1
    assert records[0]["source_row_count"] == 2
    assert sessions[0]["section_count"] == 1
    assert sessions[0]["remark_count"] == 1


def test_unresolved_outcome_is_not_reclassified_as_remark() -> None:
    records = merge_object_section_rows(
        [source_row("1513_25", "ПОС", False, False)]
    )
    session = build_session_rows(records)[0]

    assert session["unresolved_outcome_count"] == 1
    assert session["classified_outcome_share"] == 0.0
    assert session["remark_count"] == 0
    assert session["clean_share_classified"] == ""


def test_expert_variance_is_across_sessions_not_objects() -> None:
    records = merge_object_section_rows(
        [
            source_row("a", "КР", True, False, "2025-01-01"),
            source_row("b", "КР", True, False, "2025-01-01"),
            source_row("c", "КР", False, True, "2025-02-01"),
        ]
    )
    summary = summarize_experts(build_session_rows(records))[0]

    assert summary["session_count"] == 2
    assert summary["session_clean_share_mean"] == 0.5
    assert summary["session_clean_share_variance"] == 0.25
    assert summary["classified_session_clean_share_variance"] == 0.25
    assert summary["session_clean_share_range"] == 1.0
    assert summary["multi_object_session_count"] == 1
    assert summary["multi_object_session_clean_share_variance"] == 0.0


def test_quantile_interpolates() -> None:
    assert quantile([0.0, 1.0], 0.1) == 0.1
