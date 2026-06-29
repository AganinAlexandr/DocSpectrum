#!/usr/bin/env python3
"""Run typed, provenance-aware golden assertions over DocSpectrum artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO_ROOT / "schemas" / "golden_anchors_v1.json"
DEFAULT_ARTIFACT_ROOT = Path(r"E:\output\DocSpectrum")
DEFAULT_OUTPUT_DIR = DEFAULT_ARTIFACT_ROOT / "golden_regression_v1"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value_at(payload: Any, path: list[str]) -> Any:
    value = payload
    for part in path:
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"Missing JSON path component {part!r} in {path!r}")
        value = value[part]
    return value


def extract_selector(payload: dict[str, Any], selector: dict[str, Any], anchor_id: str) -> Any:
    if "json_path" in selector:
        return value_at(payload, selector["json_path"])
    rule = selector.get("filter")
    if not rule:
        raise ValueError(f"Selector for {anchor_id} has no json_path or filter")
    rows = value_at(payload, rule["list_path"])
    if not isinstance(rows, list):
        raise TypeError(f"Filter list_path for {anchor_id} is not a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and all(row.get(key) == expected for key, expected in rule["where"].items())
    ]
    if len(matches) != 1:
        raise ValueError(f"Anchor {anchor_id} expected one filtered row, found {len(matches)}")
    return value_at(matches[0], rule["value_path"])


def extract_value(payload: dict[str, Any], anchor: dict[str, Any]) -> Any:
    operands = anchor.get("operands")
    if operands:
        names = [operand["name"] for operand in operands]
        if len(names) != len(set(names)):
            raise ValueError(f"Anchor {anchor['anchor_id']} has duplicate operand names")
        return {
            operand["name"]: extract_selector(payload, operand, anchor["anchor_id"])
            for operand in operands
        }
    return extract_selector(payload, anchor, anchor["anchor_id"])


def require_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be int or float, got {type(value).__name__}")
    return value


def evaluate(actual: Any, anchor: dict[str, Any]) -> tuple[bool, str]:
    operator = anchor["operator"]
    if operator == "equal":
        expected = anchor["expected"]
        passed = type(actual) is type(expected) and actual == expected
        return passed, (
            f"actual={actual!r} ({type(actual).__name__}); "
            f"expected={expected!r} ({type(expected).__name__})"
        )
    if operator == "approx":
        value = require_number(actual, "actual")
        expected = require_number(anchor["expected"], "expected")
        tolerance = require_number(anchor["tolerance"], "tolerance")
        delta = abs(value - expected)
        return delta <= tolerance, (
            f"actual={value}; expected={expected}; tolerance={tolerance}; delta={delta}"
        )
    if operator == "between":
        value = require_number(actual, "actual")
        minimum = require_number(anchor["minimum"], "minimum")
        maximum = require_number(anchor["maximum"], "maximum")
        return minimum <= value <= maximum, f"actual={value}; range=[{minimum}, {maximum}]"
    if operator == "at_least":
        value = require_number(actual, "actual")
        minimum = require_number(anchor["minimum"], "minimum")
        return value >= minimum, f"actual={value}; minimum={minimum}"
    if operator == "sum_equal":
        if not isinstance(actual, dict):
            raise TypeError("sum_equal actual must be an operand mapping")
        values = [require_number(value, f"operand {name}") for name, value in actual.items()]
        total = sum(values)
        expected = require_number(anchor["expected"], "expected")
        passed = type(total) is type(expected) and total == expected
        return passed, f"operands={actual}; total={total}; expected={expected}"
    if operator == "difference_at_least":
        if not isinstance(actual, dict):
            raise TypeError("difference_at_least actual must be an operand mapping")
        left_name = anchor["left_operand"]
        right_name = anchor["right_operand"]
        left = require_number(actual[left_name], f"operand {left_name}")
        right = require_number(actual[right_name], f"operand {right_name}")
        minimum = require_number(anchor["minimum_difference"], "minimum_difference")
        difference = left - right
        passed = difference >= minimum
        return passed, (
            f"{left_name}={left}; {right_name}={right}; "
            f"difference={difference}; minimum_difference={minimum}"
        )
    raise ValueError(f"Unsupported operator: {operator}")


def run(spec_path: Path, artifact_root: Path, output_dir: Path) -> dict[str, Any]:
    spec = read_json(spec_path)
    cache: dict[Path, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for anchor in spec["anchors"]:
        artifact_path = artifact_root / anchor["artifact"]
        provenance = anchor.get("provenance", {})
        row = {
            "anchor_id": anchor["anchor_id"],
            "validates": anchor["validates"],
            "artifact": str(artifact_path),
            "operator": anchor["operator"],
            "actual": "",
            "status": "failed",
            "detail": "",
            "meaning": anchor["meaning"],
            "origin_review": provenance.get("origin_review", ""),
            "reviewed_value_status": provenance.get("reviewed_value_status", ""),
            "stability_mode": anchor["stability_mode"],
        }
        try:
            if artifact_path not in cache:
                cache[artifact_path] = read_json(artifact_path)
            actual = extract_value(cache[artifact_path], anchor)
            passed, detail = evaluate(actual, anchor)
            row["actual"] = actual
            row["status"] = "passed" if passed else "failed"
            row["detail"] = detail
        except Exception as exc:  # noqa: BLE001
            row["detail"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    status_counts = Counter(row["status"] for row in rows)
    validation_counts = Counter(row["validates"] for row in rows)
    summary = {
        "schema_version": "golden_regression_v1",
        "generated_at": now(),
        "spec_path": str(spec_path),
        "artifact_root": str(artifact_root),
        "anchor_count": len(rows),
        "passed_count": status_counts["passed"],
        "failed_count": status_counts["failed"],
        "validation_kind_counts": dict(sorted(validation_counts.items())),
        "all_passed": status_counts["failed"] == 0,
        "scope": "frozen_artifact_regression_not_new_model_accuracy",
        "files": {"results": "golden_regression_results_v1.csv"},
    }
    fields = [
        "anchor_id", "validates", "artifact", "operator", "actual", "status", "detail",
        "meaning", "origin_review", "reviewed_value_status", "stability_mode",
    ]
    write_csv(output_dir / "golden_regression_results_v1.csv", rows, fields)
    write_json(output_dir / "golden_regression_v1.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--assert-reference", action="store_true")
    args = parser.parse_args(argv)
    summary = run(args.spec, args.artifact_root, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if args.assert_reference and not summary["all_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
