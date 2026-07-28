from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .config import FrameAnnotationConfig
from .io import atomic_write_json, contained_path, read_json
from .models import jsonable
from .render import format_timestamp


def scene_slug(title: str, fallback: str, max_chars: int = 64) -> str:
    """Create a readable, Unicode-preserving, path-safe scene label."""
    normalized = unicodedata.normalize("NFKC", title).strip()
    normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "-", normalized)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip(" .-_")
    value = (normalized or fallback)[:max_chars].rstrip(" .-_") or fallback
    while len(value.encode("utf-8")) > 180:
        value = value[:-1].rstrip(" .-_")
    return value or fallback


def filename_timestamp(seconds: float) -> str:
    return format_timestamp(seconds).replace(":", "-").replace(".", "-")


def _font(config: FrameAnnotationConfig, height: int) -> ImageFont.ImageFont:
    size = max(12, round(height * config.font_size_ratio))
    candidates = [
        config.font_path,
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_label(
    draw: ImageDraw.ImageDraw,
    timestamp: str,
    title: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    prefix = timestamp
    if not title:
        return prefix
    candidate = f"{prefix}  |  {title}"
    while title and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
        title = title[:-1].rstrip()
        candidate = f"{prefix}  |  {title}…" if title else prefix
    return candidate


def annotate_frame(
    source: Path,
    destination: Path,
    timestamp: str,
    scene_title: str,
    config: FrameAnnotationConfig,
) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
    if config.overlay_timestamp or config.overlay_scene_title:
        font = _font(config, image.height)
        draw = ImageDraw.Draw(image)
        title = scene_title if config.overlay_scene_title else ""
        stamp = timestamp if config.overlay_timestamp else ""
        label = _fit_label(draw, stamp, title, font, max(40, image.width - 32))
        box = draw.textbbox((0, 0), label, font=font, stroke_width=1)
        text_height = box[3] - box[1]
        padding_x = max(8, round(image.width * 0.012))
        padding_y = max(6, round(image.height * 0.012))
        top = max(0, image.height - text_height - padding_y * 2)
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle((0, top, image.width, image.height), fill=(0, 0, 0, 178))
        overlay_draw.text(
            (padding_x, top + padding_y),
            label,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 255),
        )
        image = Image.alpha_composite(image, overlay)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    image.convert("RGB").save(temporary, format="JPEG", quality=config.jpeg_quality)
    temporary.replace(destination)


def _segment_dicts(segments: Iterable[Any]) -> list[dict[str, Any]]:
    return [jsonable(segment) for segment in segments]


def render_frame_annotations(
    run_dir: Path,
    segments: Iterable[Any],
    config: FrameAnnotationConfig,
) -> list[dict[str, Any]]:
    """Annotate canonical frames in place and write JSON, CSV, and Markdown indexes."""
    if not config.enabled:
        return []
    frames_dir = run_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    legacy_annotated_dir = frames_dir / "annotated"
    if legacy_annotated_dir.exists():
        for stale in legacy_annotated_dir.glob("*.jpg"):
            stale.unlink()
        try:
            legacy_annotated_dir.rmdir()
        except OSError:
            pass
    source = read_json(run_dir / "source.json")
    average_fps = source.get("average_fps")
    rows: list[dict[str, Any]] = []
    for index, segment in enumerate(_segment_dicts(segments), start=1):
        frame = segment.get("representative_frame")
        if not frame:
            continue
        timestamp_s = float(frame["timestamp_s"])
        timestamp = format_timestamp(timestamp_s)
        canonical = contained_path(run_dir, str(frame["path"]))
        scene_title = str(segment.get("title") or "")

        # Find existing annotated frame file (could be renamed to scene-aware name)
        if config.scene_aware_filenames and scene_title:
            slug = scene_slug(scene_title, f"segment-{index:04d}", config.max_scene_filename_chars)
            timestamp_part = filename_timestamp(timestamp_s)
            expected_filename = f"{index:04d}__{timestamp_part}__{slug}.jpg"
            expected_path = frames_dir / expected_filename
        else:
            expected_path = canonical

        # If expected file doesn't exist, try to find any existing frame file for this segment
        source_frame = expected_path if expected_path.exists() else canonical
        if not source_frame.exists():
            # Fallback: find any frame file matching this segment
            for existing in frames_dir.glob("*.jpg"):
                if f"segment-{index:04d}" in existing.name or existing.name.startswith(f"{index:04d}__"):
                    source_frame = existing
                    break

        # Re-annotate the frame
        if source_frame.exists():
            annotate_frame(source_frame, source_frame, timestamp, scene_title, config)

        # Rename to scene-aware filename if enabled
        if config.scene_aware_filenames and scene_title:
            slug = scene_slug(scene_title, f"segment-{index:04d}", config.max_scene_filename_chars)
            timestamp_part = filename_timestamp(timestamp_s)
            new_filename = f"{index:04d}__{timestamp_part}__{slug}.jpg"
            new_path = frames_dir / new_filename
            if source_frame != new_path:
                source_frame.rename(new_path)
            filename = new_filename
        else:
            filename = source_frame.name

        rows.append(
            {
                "index": index,
                "segment_id": segment["id"],
                "scene_title": segment.get("title"),
                "segment_start_s": float(segment["start_s"]),
                "segment_end_s": float(segment["end_s"]),
                "frame_timestamp_s": timestamp_s,
                "frame_timestamp": timestamp,
                "source_frame_number_estimate": (
                    round(timestamp_s * float(average_fps)) if average_fps else None
                ),
                "frame_path": str(frame["path"]),
                "annotated_filename": filename,
                "quality_score": frame.get("quality_score"),
                "selection_reason": frame.get("selection_reason"),
                "needs_review": bool(frame.get("needs_review")),
            }
        )
    atomic_write_json(
        frames_dir / "index.json",
        {
            "schema_version": "2.0",
            "output_mode": "annotated_only",
            "frame_count": len(rows),
            "frames": rows,
        },
    )
    fields = list(rows[0]) if rows else [
        "index", "segment_id", "scene_title", "segment_start_s", "segment_end_s",
        "frame_timestamp_s", "frame_timestamp", "source_frame_number_estimate",
        "frame_path", "annotated_filename", "quality_score", "selection_reason",
        "needs_review",
    ]
    with (frames_dir / "index.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    markdown = [
        "# Representative frame index", "",
        "| # | Timestamp | Scene | Segment | Annotated frame |",
        "|---:|---|---|---|---|",
    ]
    for row in rows:
        title = str(row["scene_title"] or "").replace("|", "\\|")
        markdown.append(
            f"| {row['index']} | {row['frame_timestamp']} | {title} | "
            f"{row['segment_id']} | [{row['annotated_filename']}]({row['annotated_filename']}) |"
        )
    (frames_dir / "index.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return rows
