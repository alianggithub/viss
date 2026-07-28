from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import contained_path, read_json


def validate_run(run_dir: Path) -> list[str]:
    errors: list[str] = []
    required = [
        "source.json", "config.json", "segments.json", "chapters.md", "key-points.md",
        "transcript/transcript.json",
    ]
    for relative in required:
        if not (run_dir / relative).is_file():
            errors.append(f"missing required output: {relative}")
    if errors:
        return errors
    try:
        source: dict[str, Any] = read_json(run_dir / "source.json")
        config: dict[str, Any] = read_json(run_dir / "config.json")
        payload: dict[str, Any] = read_json(run_dir / "segments.json")
        segments = payload["segments"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"invalid JSON output: {exc}"]
    duration = float(source["duration_s"])
    previous_end = 0.0
    seen: set[str] = set()
    for index, segment in enumerate(segments):
        label = segment.get("id", f"index {index}")
        if label in seen:
            errors.append(f"duplicate segment id: {label}")
        seen.add(label)
        start, end = float(segment["start_s"]), float(segment["end_s"])
        if start < -1e-6 or end <= start or end > duration + 0.1:
            errors.append(f"invalid interval for {label}: {start}..{end}")
        if index and abs(start - previous_end) > 0.1:
            errors.append(f"coverage gap or overlap before {label}: {previous_end}..{start}")
        previous_end = end
        frame = segment.get("representative_frame")
        if frame:
            try:
                path = contained_path(run_dir, frame["path"])
                if not path.is_file():
                    errors.append(f"missing frame for {label}: {frame['path']}")
                timestamp = float(frame["timestamp_s"])
                if not start - 0.1 <= timestamp <= end + 0.1:
                    errors.append(f"frame timestamp outside {label}")
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"invalid frame path for {label}: {exc}")
    if segments and abs(previous_end - duration) > 0.1:
        errors.append(f"segments do not cover media end: {previous_end} != {duration}")

    annotation_config = config.get("frame_annotation")
    annotation_enabled = bool(annotation_config and annotation_config.get("enabled", True))
    if annotation_enabled:
        for relative in ("frames/index.json", "frames/index.csv", "frames/index.md"):
            if not (run_dir / relative).is_file():
                errors.append(f"missing frame annotation output: {relative}")
        index_path = run_dir / "frames/index.json"
        if index_path.is_file():
            try:
                frame_index = read_json(index_path)
                rows = frame_index["frames"]
                expected = sum(bool(item.get("representative_frame")) for item in segments)
                if len(rows) != expected or int(frame_index["frame_count"]) != expected:
                    errors.append(f"frame index count mismatch: {len(rows)} != {expected}")
                for row in rows:
                    frame_path = row.get("annotated_filename") or row.get("frame_path") or row.get("annotated_path")
                    if not frame_path:
                        errors.append(f"frame index row lacks frame_path: {row.get('segment_id')}")
                        continue
                    # annotated_filename is just the filename, frames are in frames/ subdirectory
                    if not frame_path.startswith("frames/"):
                        frame_path = "frames/" + frame_path
                    annotated = contained_path(run_dir, frame_path)
                    if not annotated.is_file():
                        errors.append(
                            f"missing annotated frame for {row.get('segment_id')}: {frame_path}"
                        )
                if frame_index.get("output_mode") == "annotated_only":
                    legacy = run_dir / "frames" / "annotated"
                    if legacy.exists() and any(legacy.glob("*.jpg")):
                        errors.append("annotated-only run contains duplicate annotated frame set")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"invalid frame annotation index: {exc}")

    summary_config = config.get("summary")
    if summary_config and summary_config.get("enabled", True):
        for relative in ("summary.json", "summary.md"):
            if not (run_dir / relative).is_file():
                errors.append(f"missing summary output: {relative}")
        summary_path = run_dir / "summary.json"
        if summary_path.is_file():
            try:
                summary = read_json(summary_path)
                if int(summary["key_point_count"]) != len(summary["key_points"]):
                    errors.append("summary key-point count mismatch")
                if int(summary["chapter_count"]) != len(summary["chapters"]):
                    errors.append("summary chapter count mismatch")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"invalid summary output: {exc}")

    vision_config = config.get("vision_recognition")
    if vision_config and vision_config.get("mode", "auto") != "off":
        for relative in ("visual-descriptions.md", "evidence/vision-recognition.json"):
            if not (run_dir / relative).is_file():
                errors.append(f"missing vision-recognition output: {relative}")
    return errors
