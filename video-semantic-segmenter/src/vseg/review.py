from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from .evidence import extract_frame
from .frames import frame_quality
from .io import atomic_write_json, read_json
from .render import render_segment_dicts
from .validate import validate_run


def _now() -> str:
    return datetime.now(UTC).isoformat()


def record_override(
    run_dir: Path,
    segment_id: str,
    *,
    title: str | None = None,
    start_s: float | None = None,
    end_s: float | None = None,
    frame_timestamp_s: float | None = None,
    reviewer: str | None = None,
    verified: bool = False,
) -> None:
    raw = read_json(run_dir / "segments.raw.json")["segments"]
    if segment_id not in {segment["id"] for segment in raw}:
        raise ValueError(f"unknown segment id: {segment_id}")
    if all(value is None for value in (title, start_s, end_s, frame_timestamp_s)) and not verified:
        raise ValueError("review command contains no change")
    path = run_dir / "overrides.json"
    previous = read_json(path) if path.exists() else None
    payload = previous or {"schema_version": "1.0", "events": []}
    payload["events"].append(
        {
            "segment_id": segment_id,
            "title": title,
            "start_s": start_s,
            "end_s": end_s,
            "frame_timestamp_s": frame_timestamp_s,
            "reviewer": reviewer,
            "verified": verified,
            "created_at": _now(),
        }
    )
    atomic_write_json(path, payload)
    try:
        render_reviewed(run_dir)
    except Exception:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write_json(path, previous)
        raise


def render_reviewed(run_dir: Path) -> None:
    raw_path = run_dir / "segments.raw.json"
    if not raw_path.exists():
        raise FileNotFoundError("segments.raw.json is unavailable; rerun analysis first")
    segments: list[dict[str, Any]] = read_json(raw_path)["segments"]
    overrides = run_dir / "overrides.json"
    events = read_json(overrides).get("events", []) if overrides.exists() else []
    by_id = {segment["id"]: index for index, segment in enumerate(segments)}
    source = read_json(run_dir / "source.json")
    for event in events:
        index = by_id.get(event["segment_id"])
        if index is None:
            raise ValueError(f"override references unknown segment: {event['segment_id']}")
        segment = segments[index]
        if event.get("title") is not None:
            title = event["title"].strip()
            if not title:
                raise ValueError("review title cannot be empty")
            segment["title"] = title
            segment["title_confidence"] = 1.0 if event.get("verified") else None
        if event.get("start_s") is not None:
            start = float(event["start_s"])
            if index == 0 and abs(start) > 1e-6:
                raise ValueError("first segment must start at zero")
            if not 0 <= start < float(segment["end_s"]):
                raise ValueError("reviewed start is outside its segment")
            segment["start_s"] = start
            if index:
                segments[index - 1]["end_s"] = start
        if event.get("end_s") is not None:
            end = float(event["end_s"])
            if not float(segment["start_s"]) < end <= float(source["duration_s"]):
                raise ValueError("reviewed end is outside source duration")
            segment["end_s"] = end
            if index + 1 < len(segments):
                segments[index + 1]["start_s"] = end
        if event.get("frame_timestamp_s") is not None:
            timestamp = float(event["frame_timestamp_s"])
            if not float(segment["start_s"]) <= timestamp <= float(segment["end_s"]):
                raise ValueError("reviewed frame timestamp is outside the segment")
            actual, bgr = extract_frame(Path(source["path"]), timestamp)
            if actual > float(segment["end_s"]) + 0.1:
                raise ValueError("decoder returned a frame outside the segment")
            quality, metrics = frame_quality(bgr)
            frame_path = run_dir / "frames" / f"{segment['id']}.jpg"
            Image.fromarray(bgr[:, :, ::-1]).save(frame_path, quality=90)
            segment["representative_frame"] = {
                "path": f"frames/{segment['id']}.jpg",
                "timestamp_s": actual,
                "quality_score": quality,
                "relevance_score": None,
                "selection_reason": "human_override",
                "needs_review": not event.get("verified", False),
                "candidate_scores": [{"timestamp_s": actual, "quality_score": quality, **metrics}],
            }
        if event.get("verified"):
            segment["boundary_needs_review"] = False
    render_segment_dicts(run_dir, segments)
    errors = validate_run(run_dir)
    if errors:
        raise ValueError("review overrides produce invalid output: " + "; ".join(errors))
