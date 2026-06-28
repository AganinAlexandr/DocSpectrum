#!/usr/bin/env python3
"""Run versioned golden assertions over validated DocSpectrum artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO_ROOT / "schemas" / "golden_anchors_v0.json"
DEFAULT_ARTIFACT_ROOT = Path(r"E:\output\DocSpectrum")
DEFAULT_OUTPUT_DIR = DEFAULT_ARTIFACT_ROOT / "golden_regression_v0"


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


def extract_value(payload: dict[str, Any], anchor: dict[str, Any]) -> Any:
    if "json_path" in anchor:
        return value_at(payload, anchor["json_path"])
    rule = anchor.get("filter")
    if not rule:
        raise ValueError(f"Anchor {anchor['anchor_id']} has no selector")
    rows = value_at(payload, rule["list_path"])
    if not isinstance(rows, list):
        raise TypeError(f"Filter list_path for {anchor['anchor_id']} is not a list")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and all(row.get(key) == expected for key, expected in rule["where"].items())
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Anchor {anchor['anchor_id']} expected one filtered row, found {len(matches)}"
        )
    return value_at(matches[0], rule["value_path"])


def evaluate(actual: Any, anchor: dict[str, Any]) -> tuple[bool, str]:
    operator = anchor["operator"]
    if operator == "equal":
        passed = actual == anchor["expected"]
        return passed, f"actual={actual!r}; expected={anchor['expected']!r}"
    if operator == "approx":
        delta = abs(float(actual) - float(anchor["expected"]))
        passed = delta <= float(anchor["tolerance"])
        return passed, (
            f"actual={actual}; expected={anchor['expected']}; "
            f"tolerance={anchor['tolerance']}; delta={delta}"
        )
    if operator == "between":
        value = float(actual)
        minimum = float(anchor["minimum"])
        maximum = float(anchor["maximum"])
        passed = minimum <= value <= maximum
        return passed, f"actual={actual}; range=[{minimum}, {maximum}]"
    raise ValueError(f"Unsupported operator: {operator}")


def run(spec_path: Path, artifact_root: Path, output_dir: Path) -> dict[str, Any]:
    spec = read_json(spec_path)
    cache: dict[Path, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for anchor in spec["anchors"]:
        artifact_path = artifact_root / anchor["artifact"]
        row = {
            "anchor_id": anchor["anchor_id"],
            "validates": anchor["validates"],
            "artifact": str(artifact_path),
            "operator": anchor["operator"],
            "actual": "",
            "status": "failed",
            "detail": "",
            "meaning": anchor["meaning"],
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
        "schema_version": "golden_regression_v0",
        "generated_at": now(),
        "spec_path": str(spec_path),
        "artifact_root": str(artifact_root),
        "anchor_count": len(rows),
        "passed_count": status_counts["passed"],
        "failed_count": status_counts["failed"],
        "validation_kind_counts": dict(sorted(validation_counts.items())),
        "all_passed": status_counts["failed"] == 0,
        "scope": "validated_behavior_regression_not_new_model_accuracy",
        "files": {"results": "golden_regression_results_v0.csv"},
    }
    write_csv(
        output_dir / "golden_regression_results_v0.csv",
        rows,
        ["anchor_id", "validates", "artifact", "operator", "actual", "status", "detail", "meaning"],
    )
    write_json(output_dir / "golden_regression_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--assert-reference", action="store_true")
    args = parser.parse_args()
    summary = run(args.spec, args.artifact_root, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.assert_reference and not summary["all_passed"]:
        raise SystemExit(f"Golden regression failed: {summary['failed_count']} anchors")


if __name__ == "__main__":
    main()
