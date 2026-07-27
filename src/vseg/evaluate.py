from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .io import atomic_write_json, read_json


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def evaluate_run(run_dir: Path, reference_path: Path) -> dict[str, Any]:
    predicted = read_json(run_dir / "segments.json")["segments"]
    expected = read_json(reference_path)["segments"]
    available = set(range(len(predicted)))
    matches: list[dict[str, Any]] = []
    errors: list[float] = []
    accepted_frames = 0
    exact_titles = 0
    for reference in expected:
        tolerance = float(reference.get("boundary_tolerance_s", 10.0))
        choices = sorted(
            (
                (abs(float(predicted[index]["start_s"]) - float(reference["start_s"])), index)
                for index in available
            ),
            key=lambda item: item[0],
        )
        if not choices or choices[0][0] > tolerance:
            matches.append({"reference": reference["title"], "matched": False})
            continue
        error, index = choices[0]
        available.remove(index)
        segment = predicted[index]
        errors.append(error)
        exact_titles += segment["title"].casefold().strip() == reference["title"].casefold().strip()
        frame = segment.get("representative_frame")
        ranges = reference.get("acceptable_frame_ranges", [])
        frame_ok = bool(
            frame
            and any(
                float(start) <= float(frame["timestamp_s"]) <= float(end) for start, end in ranges
            )
        )
        accepted_frames += frame_ok
        matches.append(
            {
                "reference": reference["title"],
                "matched": True,
                "predicted_id": segment["id"],
                "boundary_error_s": error,
                "title_exact": segment["title"].casefold().strip()
                == reference["title"].casefold().strip(),
                "frame_accepted": frame_ok,
            }
        )
    true_positive = len(errors)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    result = {
        "schema_version": "1.0",
        "reference": str(reference_path.resolve()),
        "predicted_count": len(predicted),
        "reference_count": len(expected),
        "topic_precision": precision,
        "topic_recall": recall,
        "topic_f1": f1,
        "median_boundary_error_s": _percentile(errors, 0.5),
        "p90_boundary_error_s": _percentile(errors, 0.9),
        "exact_title_accuracy": exact_titles / true_positive if true_positive else 0.0,
        "representative_frame_acceptance": (
            accepted_frames / true_positive if true_positive else 0.0
        ),
        "matches": matches,
    }
    atomic_write_json(run_dir / "evaluation.json", result)
    return result
