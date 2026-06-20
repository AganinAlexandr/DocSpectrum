from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_expert_quality_difficulty_v0 import (  # noqa: E402
    add_section_relative_percentiles,
    percentile_ranks,
    spearman,
    unique_arena_documents,
)


def test_percentile_ranks_use_midranks_for_ties() -> None:
    assert percentile_ranks([1.0, 1.0, 3.0]) == [0.25, 0.25, 1.0]


def test_single_value_percentile_is_neutral() -> None:
    assert percentile_ranks([10.0]) == [0.5]


def test_spearman_detects_monotonic_direction() -> None:
    assert abs(spearman([1, 2, 3], [3, 2, 1]) + 1.0) < 1e-12


def test_unique_arena_documents_deduplicates_pair_reuse() -> None:
    rows = [
        {
            "group_id": "g",
            "organization": "org",
            "work_type": "work",
            "section_code": "КР",
            "left_object_id": "a",
            "right_object_id": "b",
            "left_bundle_id": "doc_a",
            "right_bundle_id": "doc_b",
        },
        {
            "group_id": "g",
            "organization": "org",
            "work_type": "work",
            "section_code": "КР",
            "left_object_id": "a",
            "right_object_id": "c",
            "left_bundle_id": "doc_a",
            "right_bundle_id": "doc_c",
        },
    ]
    assert len(unique_arena_documents(rows)) == 3


def test_difficulty_percentile_is_section_relative() -> None:
    rows = [
        {
            "section_code": "КР",
            "page_count": 1,
            "element_count": 10,
            "elements_per_page": 10,
            "structural_elements_per_page": 5,
            "table_cells_per_page": 0,
        },
        {
            "section_code": "КР",
            "page_count": 10,
            "element_count": 100,
            "elements_per_page": 100,
            "structural_elements_per_page": 50,
            "table_cells_per_page": 10,
        },
        {
            "section_code": "ПОС",
            "page_count": 100,
            "element_count": 1000,
            "elements_per_page": 1000,
            "structural_elements_per_page": 500,
            "table_cells_per_page": 100,
        },
    ]
    add_section_relative_percentiles(rows)
    assert rows[0]["spectral_difficulty_percentile_v0"] == 0.0
    assert rows[1]["spectral_difficulty_percentile_v0"] == 1.0
    assert rows[2]["spectral_difficulty_percentile_v0"] == 0.5
