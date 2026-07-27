from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import SummaryConfig
from .io import atomic_write_json
from .models import SemanticSegment
from .render import format_timestamp


def _normalized(text: str) -> str:
    return re.sub(r"\W+", "", unicodedata.normalize("NFKC", text).lower())


def build_video_summary(segments: list[SemanticSegment], config: SummaryConfig) -> dict:
    """Build a deterministic transcript-grounded overview across all semantic segments."""
    chapters = [
        {
            "segment_id": segment.id,
            "timestamp_s": segment.start_s,
            "timestamp": format_timestamp(segment.start_s).split(".")[0],
            "title": segment.title,
        }
        for segment in segments
    ]
    points: list[dict] = []
    seen: set[str] = set()
    max_depth = max((len(segment.key_points) for segment in segments), default=0)
    for depth in range(max_depth):
        for segment in segments:
            if depth >= min(len(segment.key_points), config.max_points_per_segment):
                continue
            point = segment.key_points[depth]
            key = _normalized(point.text)
            if not key or key in seen:
                continue
            seen.add(key)
            points.append(
                {
                    "segment_id": segment.id,
                    "timestamp_s": segment.start_s,
                    "timestamp": format_timestamp(segment.start_s).split(".")[0],
                    "title": segment.title,
                    "text": point.text,
                    "evidence_refs": point.evidence_refs,
                    "confidence": point.confidence,
                }
            )
            if len(points) >= config.max_key_points:
                break
        if len(points) >= config.max_key_points:
            break
    overview_titles = [item["title"] for item in chapters[: config.max_overview_topics]]
    overview = (
        "The video covers: " + "; ".join(overview_titles) + "." if overview_titles else ""
    )
    return {
        "schema_version": "1.0",
        "provider": "vseg-transcript-extractive-v1",
        "grounding": "semantic segments and transcript evidence",
        "overview": overview,
        "chapter_count": len(chapters),
        "key_point_count": len(points),
        "chapters": chapters,
        "key_points": points,
    }


def render_video_summary(run_dir: Path, segments: list[SemanticSegment], config: SummaryConfig) -> dict:
    summary = build_video_summary(segments, config)
    atomic_write_json(run_dir / "summary.json", summary)
    lines = ["# Video summary", ""]
    if summary["overview"]:
        lines.extend([summary["overview"], ""])
    lines.extend(["## Key points", ""])
    if summary["key_points"]:
        for point in summary["key_points"]:
            stamp = f"**{point['timestamp']}** " if config.include_timestamps else ""
            lines.append(f"- {stamp}{point['text']}")
    else:
        lines.append("- No transcript-grounded key points were available.")
    lines.extend(["", "## Chapter overview", ""])
    for chapter in summary["chapters"]:
        stamp = f"{chapter['timestamp']} — " if config.include_timestamps else ""
        lines.append(f"- {stamp}{chapter['title']}")
    (run_dir / "summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return summary
