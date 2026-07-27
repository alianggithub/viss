from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np
from PIL import Image

from .config import FrameAnnotationConfig, UserFrameDumpConfig
from .frame_annotations import annotate_frame, filename_timestamp, scene_slug
from .frames import frame_quality
from .io import atomic_write_json
from .probe import probe_media
from .render import format_timestamp


@dataclass(frozen=True, slots=True)
class TimestampRequest:
    timestamp_s: float
    label: str = ""
    source: str = "command_line"
    source_line: int | None = None


@dataclass(slots=True)
class _Candidate:
    timestamp_s: float
    frame_number: int | None
    image: np.ndarray
    quality_score: float
    metrics: dict[str, float]
    proximity_score: float
    selection_score: float


_INTEGER = re.compile(r"^\d+$")


def parse_timestamp(value: str) -> float:
    """Parse whole seconds, MM:SS, or HH:MM:SS into seconds."""
    text = value.strip()
    if not text:
        raise ValueError("timestamp is empty")
    fields = text.split(":")
    if len(fields) == 1:
        if not _INTEGER.fullmatch(fields[0]):
            raise ValueError(f"invalid timestamp {value!r}; use seconds, MM:SS, or HH:MM:SS")
        return float(int(fields[0]))
    if len(fields) not in {2, 3} or any(not _INTEGER.fullmatch(item) for item in fields):
        raise ValueError(f"invalid timestamp {value!r}; use seconds, MM:SS, or HH:MM:SS")
    numbers = [int(item) for item in fields]
    if numbers[-1] >= 60 or (len(numbers) == 3 and numbers[-2] >= 60):
        raise ValueError(f"invalid timestamp {value!r}; minutes/seconds must be below 60")
    if len(numbers) == 2:
        minutes, seconds = numbers
        return float(minutes * 60 + seconds)
    hours, minutes, seconds = numbers
    return float(hours * 3600 + minutes * 60 + seconds)


def parse_request(value: str, *, source: str, source_line: int | None = None) -> TimestampRequest:
    stamp, separator, label = value.partition("|")
    return TimestampRequest(
        timestamp_s=parse_timestamp(stamp),
        label=label.strip() if separator else "",
        source=source,
        source_line=source_line,
    )


def load_timestamp_requests(values: Iterable[str], timestamps_file: Path | None = None) -> list[TimestampRequest]:
    requests = [parse_request(item, source="command_line") for item in values]
    if timestamps_file is not None:
        if not timestamps_file.is_file():
            raise FileNotFoundError(f"timestamp file not found: {timestamps_file}")
        for line_number, line in enumerate(
            timestamps_file.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                requests.append(
                    parse_request(
                        stripped,
                        source=str(timestamps_file.resolve()),
                        source_line=line_number,
                    )
                )
            except ValueError as exc:
                raise ValueError(f"{timestamps_file}:{line_number}: {exc}") from exc
    if not requests:
        raise ValueError("provide at least one --timestamp or --timestamps-file entry")
    return requests


def _normalized_weights(config: UserFrameDumpConfig) -> tuple[float, float]:
    total = config.quality_weight + config.proximity_weight
    return config.quality_weight / total, config.proximity_weight / total


def _choose_candidate(candidates: list[_Candidate], target_s: float, config: UserFrameDumpConfig) -> _Candidate:
    if not candidates:
        raise RuntimeError(f"no decodable frame found near {format_timestamp(target_s)}")
    if not config.fine_tune:
        return min(candidates, key=lambda item: (abs(item.timestamp_s - target_s), item.timestamp_s))
    return max(
        candidates,
        key=lambda item: (
            item.selection_score,
            item.quality_score,
            -abs(item.timestamp_s - target_s),
            -item.timestamp_s,
        ),
    )


def _decode_candidates(
    media_path: Path,
    target_s: float,
    duration_s: float,
    config: UserFrameDumpConfig,
) -> list[_Candidate]:
    window = config.search_window_s if config.fine_tune else max(0.25, 1 / config.sample_fps)
    start_s = max(0.0, target_s - window)
    end_s = min(duration_s, target_s + window)
    interval_s = 1.0 / config.sample_fps
    quality_weight, proximity_weight = _normalized_weights(config)
    candidates: list[_Candidate] = []
    container = av.open(str(media_path))
    stream = container.streams.video[0]
    next_sample_s = start_s
    try:
        container.seek(int(max(0.0, start_s - 1.0) * av.time_base), backward=True)
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            actual_s = float(frame.time)
            if actual_s + 1e-6 < start_s or actual_s + 1e-6 < next_sample_s:
                continue
            if actual_s > end_s + 1e-3:
                break
            image = frame.to_ndarray(format="bgr24")
            quality, metrics = frame_quality(image)
            proximity = max(0.0, 1.0 - abs(actual_s - target_s) / window) if window > 0 else 1.0
            candidates.append(
                _Candidate(
                    timestamp_s=actual_s,
                    frame_number=(
                        round(actual_s * float(stream.average_rate)) if stream.average_rate else None
                    ),
                    image=image,
                    quality_score=quality,
                    metrics=metrics,
                    proximity_score=proximity,
                    selection_score=quality_weight * quality + proximity_weight * proximity,
                )
            )
            next_sample_s = actual_s + interval_s
    finally:
        container.close()
    return candidates


def _validate_requests(requests: list[TimestampRequest], duration_s: float) -> None:
    errors = []
    for index, request in enumerate(requests, start=1):
        if request.timestamp_s > duration_s:
            location = (
                f"{request.source}:{request.source_line}"
                if request.source_line is not None
                else f"request {index}"
            )
            errors.append(
                f"{location}: {format_timestamp(request.timestamp_s)} is beyond video duration "
                f"{format_timestamp(duration_s)}"
            )
    if errors:
        raise ValueError("invalid timestamp request(s):\n- " + "\n- ".join(errors))


def _write_selected_image(
    selected: _Candidate,
    destination: Path,
    label: str,
    annotation: FrameAnnotationConfig,
) -> None:
    temporary = destination.parent / f".{destination.name}.unannotated.tmp"
    try:
        Image.fromarray(selected.image[:, :, ::-1]).save(
            temporary, format="JPEG", quality=annotation.jpeg_quality
        )
        annotate_frame(
            temporary,
            destination,
            format_timestamp(selected.timestamp_s),
            label,
            annotation,
        )
    finally:
        temporary.unlink(missing_ok=True)


def dump_user_frames(
    media_path: Path,
    output_dir: Path,
    requests: list[TimestampRequest],
    config: UserFrameDumpConfig,
    annotation: FrameAnnotationConfig,
) -> list[dict]:
    """Extract and index one quality-tuned frame for each requested timestamp."""
    media_path = media_path.resolve()
    metadata = probe_media(media_path)
    _validate_requests(requests, metadata.duration_s)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    legacy_annotated_dir = output_dir / "annotated"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for directory in (frames_dir, legacy_annotated_dir):
        if directory.exists():
            for stale in directory.glob("*.jpg"):
                stale.unlink()
    if config.annotated_only and legacy_annotated_dir.exists():
        try:
            legacy_annotated_dir.rmdir()
        except OSError:
            pass

    rows: list[dict] = []
    for index, request in enumerate(requests, start=1):
        candidates = _decode_candidates(media_path, request.timestamp_s, metadata.duration_s, config)
        selected = _choose_candidate(candidates, request.timestamp_s, config)
        label_slug = scene_slug(request.label, "frame", annotation.max_scene_filename_chars)
        base = (
            f"{index:04d}__requested-{filename_timestamp(request.timestamp_s)}"
            f"__actual-{filename_timestamp(selected.timestamp_s)}"
        )
        if request.label:
            base += f"__{label_slug}"
        filename = f"{base}.jpg"
        raw_path: str | None = None
        annotated_path: str | None = None
        if config.annotated_only:
            destination = frames_dir / filename
            _write_selected_image(selected, destination, request.label, annotation)
            frame_path = f"frames/{filename}"
        else:
            legacy_annotated_dir.mkdir(parents=True, exist_ok=True)
            raw = frames_dir / filename
            Image.fromarray(selected.image[:, :, ::-1]).save(
                raw, format="JPEG", quality=annotation.jpeg_quality
            )
            annotated = legacy_annotated_dir / filename
            annotate_frame(
                raw, annotated, format_timestamp(selected.timestamp_s), request.label, annotation
            )
            raw_path = f"frames/{filename}"
            annotated_path = f"annotated/{filename}"
            frame_path = annotated_path
        row = {
            "index": index,
            "label": request.label or None,
            "requested_timestamp_s": request.timestamp_s,
            "requested_timestamp": format_timestamp(request.timestamp_s),
            "selected_timestamp_s": selected.timestamp_s,
            "selected_timestamp": format_timestamp(selected.timestamp_s),
            "offset_s": round(selected.timestamp_s - request.timestamp_s, 6),
            "source_frame_number_estimate": selected.frame_number,
            "frame_path": frame_path,
            "quality_score": round(selected.quality_score, 6),
            "proximity_score": round(selected.proximity_score, 6),
            "selection_score": round(selected.selection_score, 6),
            "selection_reason": (
                "best_quality_proximity_score" if config.fine_tune else "nearest_decoded_frame"
            ),
            "needs_review": selected.quality_score < config.min_quality,
            "request_source": request.source,
            "request_source_line": request.source_line,
            "candidate_count": len(candidates),
            "candidate_scores": [
                {
                    "timestamp_s": item.timestamp_s,
                    "quality_score": round(item.quality_score, 6),
                    "proximity_score": round(item.proximity_score, 6),
                    "selection_score": round(item.selection_score, 6),
                    **item.metrics,
                }
                for item in candidates
            ],
        }
        if raw_path is not None:
            row["raw_path"] = raw_path
            row["annotated_path"] = annotated_path
        rows.append(row)

    manifest = {
        "schema_version": "1.1",
        "source": {
            "path": str(media_path),
            "sha256": metadata.sha256,
            "duration_s": metadata.duration_s,
            "average_fps": metadata.average_fps,
        },
        "output_mode": "annotated_only" if config.annotated_only else "raw_and_annotated",
        "selection": {
            "fine_tune": config.fine_tune,
            "search_window_s": config.search_window_s,
            "sample_fps": config.sample_fps,
            "quality_weight": config.quality_weight,
            "proximity_weight": config.proximity_weight,
            "min_quality": config.min_quality,
        },
        "frame_count": len(rows),
        "frames": rows,
    }
    atomic_write_json(output_dir / "index.json", manifest)
    fields = [
        "index", "label", "requested_timestamp_s", "requested_timestamp",
        "selected_timestamp_s", "selected_timestamp", "offset_s",
        "source_frame_number_estimate", "frame_path", "quality_score", "proximity_score",
        "selection_score", "selection_reason", "needs_review", "request_source",
        "request_source_line", "candidate_count",
    ]
    with (output_dir / "index.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in rows)
    markdown = [
        "# User-requested frame index", "",
        "| # | Requested | Selected | Offset | Label | Frame | Review |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for row in rows:
        label = str(row["label"] or "").replace("|", "\\|")
        review = "yes" if row["needs_review"] else "no"
        markdown.append(
            f"| {row['index']} | {row['requested_timestamp']} | {row['selected_timestamp']} | "
            f"{row['offset_s']:+.3f}s | {label} | [image]({row['frame_path']}) | {review} |"
        )
    (output_dir / "index.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return rows
