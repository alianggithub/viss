from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any

from .config import Config
from .io import atomic_write_json, read_json
from .models import EvidenceEvent, SemanticSegment, jsonable
from .render import format_timestamp


def slugify(text: str, max_chars: int = 64) -> str:
    """Create a filesystem-safe slug from text, preserving Unicode."""
    normalized = unicodedata.normalize("NFKC", text).strip()
    # Replace filesystem-invalid chars and common punctuation with dashes
    normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f!@#$%^&*()\[\]{}'`,;=+]", "-", normalized)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip(" .-_")
    value = normalized[:max_chars].rstrip(" .-_")
    while len(value.encode("utf-8")) > 180:
        value = value[:-1].rstrip(" .-_")
    return value or "untitled"


def generate_video_title(segments: list[SemanticSegment], vision_events: list[EvidenceEvent]) -> str | None:
    """Generate a descriptive title from segment titles and vision descriptions."""
    # Collect all segment titles
    titles = [seg.title for seg in segments if seg.title]
    if not titles:
        return None

    # Also collect vision descriptions if available
    descriptions = [evt.payload.get("description", "") for evt in vision_events if evt.payload]

    # Combine and create a concise title
    # Use the first few segment titles, joined
    title_parts = []
    for title in titles[:3]:  # Use up to first 3 segments
        slug = slugify(title, max_chars=30)
        if slug:
            title_parts.append(slug)

    if not title_parts:
        return None

    # Join with dashes, limit total length
    combined = "-".join(title_parts)
    return slugify(combined, max_chars=80)


def copy_source_video(source_path: Path, run_dir: Path) -> Path:
    """Copy the source video into the run directory."""
    dest = run_dir / f"{run_dir.name}{source_path.suffix}"
    if not dest.exists():
        shutil.copy2(source_path, dest)
    return dest


def rename_run_directory(run_dir: Path, new_name: str, config: Config) -> Path:
    """Rename the run directory and update all internal references."""
    parent = run_dir.parent
    new_dir = parent / new_name

    if new_dir.exists():
        # Already renamed or conflict
        return run_dir

    # Rename the directory
    run_dir.rename(new_dir)

    # Update source.json with new path
    source_json = new_dir / "source.json"
    if source_json.exists():
        source = read_json(source_json)
        source["path"] = str(new_dir / Path(source["path"]).name)
        atomic_write_json(source_json, source)

    # Update config.json if it has output references
    config_json = new_dir / "config.json"
    if config_json.exists():
        cfg = read_json(config_json)
        # No path references in config.json typically
        atomic_write_json(config_json, cfg)

    # Update run.json
    run_json = new_dir / "run.json"
    if run_json.exists():
        run_data = read_json(run_json)
        atomic_write_json(run_json, run_data)

    # Rename video file inside if it matches old name
    old_stem = run_dir.name
    for ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
        old_video = new_dir / f"{old_stem}{ext}"
        if old_video.exists():
            new_video = new_dir / f"{new_name}{ext}"
            old_video.rename(new_video)
            # Update source.json again
            if source_json.exists():
                source = read_json(source_json)
                source["path"] = str(new_video)
                atomic_write_json(source_json, source)
            break

    # Rename output subdirectories (viss-analysis, viss-analysis-nemotron, etc.)
    for subdir in new_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith(old_stem):
            new_subdir_name = subdir.name.replace(old_stem, new_name, 1)
            new_subdir = new_dir / new_subdir_name
            subdir.rename(new_subdir)
            
            # Update segments.json inside the renamed analysis directory
            segments_json = new_subdir / "segments.json"
            if segments_json.exists():
                segments_data = read_json(segments_json)
                for segment in segments_data.get("segments", []):
                    frame = segment.get("representative_frame")
                    if frame and "path" in frame:
                        frame["path"] = frame["path"].replace(old_stem, new_name, 1)
                atomic_write_json(segments_json, segments_data)
                
                # Also update segments.raw.json
                segments_raw = new_subdir / "segments.raw.json"
                if segments_raw.exists():
                    segments_raw_data = read_json(segments_raw)
                    for segment in segments_raw_data.get("segments", []):
                        frame = segment.get("representative_frame")
                        if frame and "path" in frame:
                            frame["path"] = frame["path"].replace(old_stem, new_name, 1)
                    atomic_write_json(segments_raw, segments_raw_data)

    # Update all index files in frames/ directory
    frames_dir = new_dir / "frames"
    if frames_dir.exists():
        update_index_files(frames_dir, old_stem, new_name)

    # Update index files in any analysis subdirectories
    for subdir in new_dir.iterdir():
        if subdir.is_dir() and "analysis" in subdir.name:
            frames_subdir = subdir / "frames"
            if frames_subdir.exists():
                update_index_files(frames_subdir, old_stem, new_name)

    return new_dir


def update_index_files(frames_dir: Path, old_stem: str, new_name: str) -> None:
    """Update all index.json, index.csv, index.md files to reflect new paths."""
    # Update index.json
    index_json = frames_dir / "index.json"
    if index_json.exists():
        data = read_json(index_json)
        for frame in data.get("frames", []):
            for key in ["frame_path", "annotated_filename"]:
                if key in frame and isinstance(frame[key], str):
                    frame[key] = frame[key].replace(old_stem, new_name, 1)
        atomic_write_json(index_json, data)

    # Update index.csv
    index_csv = frames_dir / "index.csv"
    if index_csv.exists():
        import csv
        rows = []
        with index_csv.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key in ["frame_path", "annotated_filename"]:
                    if key in row and isinstance(row[key], str):
                        row[key] = row[key].replace(old_stem, new_name, 1)
                rows.append(row)
        if rows:
            with index_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

    # Update index.md
    index_md = frames_dir / "index.md"
    if index_md.exists():
        content = index_md.read_text(encoding="utf-8")
        content = content.replace(old_stem, new_name)
        index_md.write_text(content, encoding="utf-8")


def organize_existing_flat_layout(root: Path, config: Config) -> list[Path]:
    """Organize existing flat layout into per-video folders. Returns list of created video folders."""
    created = []
    root = root.expanduser().resolve()

    # Find all video files directly in root
    video_extensions = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    video_files = [f for f in root.iterdir() if f.is_file() and f.suffix.lower() in video_extensions]

    for video_file in video_files:
        video_stem = video_file.stem
        video_folder = root / video_stem

        # Skip if already organized
        if video_folder.exists():
            continue

        video_folder.mkdir(parents=True, exist_ok=True)

        # Move video file
        new_video_path = video_folder / video_file.name
        video_file.rename(new_video_path)

        # Find and move associated analysis directories
        for ext_dir in root.iterdir():
            if ext_dir.is_dir() and ext_dir.name.startswith(video_stem + "-"):
                new_ext_dir = video_folder / ext_dir.name
                ext_dir.rename(new_ext_dir)

        created.append(video_folder)

    return created


def post_analysis_organize(
    run_dir: Path,
    config: Config,
    segments: list[SemanticSegment],
    vision_events: list[EvidenceEvent],
    title_override: str | None = None,
) -> Path:
    """Organize and rename after analysis completes. Returns final run directory path."""
    if not config.output.organize_by_default:
        return run_dir

    # Copy source video into run directory if not already there
    source = read_json(run_dir / "source.json")
    source_path = Path(source["path"])
    if source_path.parent != run_dir:
        copy_source_video(source_path, run_dir)

    # Use title override if provided, otherwise generate from analysis results
    if config.output.rename_after_analysis:
        title = title_override or generate_video_title(segments, vision_events)
        if title and title != run_dir.name:
            run_dir = rename_run_directory(run_dir, title, config)
            # Also rename parent video folder if it matches the original video stem
            parent = run_dir.parent
            # The parent folder should be the video folder (e.g., chrome_bJDF3yGuLE/)
            # Check if parent name matches the original video stem
            original_video_stem = source_path.stem
            if parent.name == original_video_stem and parent != run_dir:
                new_parent = parent.parent / title
                if not new_parent.exists():
                    parent.rename(new_parent)
                    run_dir = new_parent / title

    return run_dir