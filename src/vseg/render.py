from __future__ import annotations

from pathlib import Path

from .io import atomic_write_json
from .models import SemanticSegment, Transcript, jsonable


def format_timestamp(seconds: float, srt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_transcript(run_dir: Path, transcript: Transcript) -> None:
    directory = run_dir / "transcript"
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(directory / "transcript.json", jsonable(transcript))
    lines = [segment.text for segment in transcript.segments if segment.text]
    (directory / "transcript.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    markdown = ["# Transcript", ""]
    markdown.extend(
        f"- **{format_timestamp(segment.start_s)}** {segment.text}"
        for segment in transcript.segments
        if segment.text
    )
    (directory / "transcript.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    srt: list[str] = []
    vtt = ["WEBVTT", ""]
    for index, segment in enumerate(transcript.segments, 1):
        srt_interval = (
            f"{format_timestamp(segment.start_s, True)} --> {format_timestamp(segment.end_s, True)}"
        )
        srt.extend(
            [
                str(index),
                srt_interval,
                segment.text,
                "",
            ]
        )
        vtt.extend(
            [
                f"{format_timestamp(segment.start_s)} --> {format_timestamp(segment.end_s)}",
                segment.text,
                "",
            ]
        )
    (directory / "transcript.srt").write_text("\n".join(srt), encoding="utf-8")
    (directory / "transcript.vtt").write_text("\n".join(vtt), encoding="utf-8")


def render_segments(run_dir: Path, segments: list[SemanticSegment]) -> None:
    atomic_write_json(
        run_dir / "segments.json", {"schema_version": "1.0", "segments": jsonable(segments)}
    )
    chapters = ["# Video chapters", ""]
    key_points = ["# Key points", ""]
    for segment in segments:
        stamp = format_timestamp(segment.start_s).split(".")[0]
        chapters.append(f"- {stamp} — {segment.title}")
        if segment.key_points:
            key_points.append(f"## {stamp} — {segment.title}")
            key_points.append("")
            key_points.extend(f"- {point.text}" for point in segment.key_points)
            key_points.append("")
    (run_dir / "chapters.md").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    (run_dir / "key-points.md").write_text("\n".join(key_points) + "\n", encoding="utf-8")


def render_segment_dicts(run_dir: Path, segments: list[dict]) -> None:
    """Render reviewed segment dictionaries without altering raw analysis artifacts."""
    atomic_write_json(run_dir / "segments.json", {"schema_version": "1.0", "segments": segments})
    chapters = ["# Video chapters", ""]
    key_points = ["# Key points", ""]
    for segment in segments:
        stamp = format_timestamp(float(segment["start_s"])).split(".")[0]
        chapters.append(f"- {stamp} — {segment['title']}")
        points = segment.get("key_points", [])
        if points:
            key_points.extend([f"## {stamp} — {segment['title']}", ""])
            key_points.extend(f"- {point['text']}" for point in points)
            key_points.append("")
    (run_dir / "chapters.md").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    (run_dir / "key-points.md").write_text("\n".join(key_points) + "\n", encoding="utf-8")


def render_report(run_dir: Path, segments: list[SemanticSegment], warnings: list[str]) -> None:
    review_count = sum(
        item.boundary_needs_review
        or (item.representative_frame and item.representative_frame.needs_review)
        for item in segments
    )
    lines = [
        "# Video semantic analysis report",
        "",
        f"- Segments: {len(segments)}",
        f"- Items needing review: {review_count}",
        f"- Warnings: {len(warnings)}",
    ]
    if warnings:
        lines.extend(["", "## Warnings", "", *(f"- {warning}" for warning in warnings)])
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
