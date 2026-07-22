from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

from vseg.cli import main
from vseg.config import Config, FrameAnnotationConfig
from vseg.frame_annotations import render_frame_annotations, scene_slug
from vseg.io import atomic_write_json, read_json


def _run(tmp_path: Path) -> tuple[Path, list[dict]]:
    run = tmp_path / "run"
    (run / "frames").mkdir(parents=True)
    image = np.full((120, 240, 3), (80, 140, 200), dtype=np.uint8)
    Image.fromarray(image).save(run / "frames" / "segment-0001.jpg")
    atomic_write_json(
        run / "source.json",
        {"duration_s": 60.0, "average_fps": 30.0},
    )
    segments = [
        {
            "id": "segment-0001",
            "start_s": 10.0,
            "end_s": 30.0,
            "title": "神奇 美景 / Guilin",
            "representative_frame": {
                "path": "frames/segment-0001.jpg",
                "timestamp_s": 12.345,
                "quality_score": 0.91,
                "selection_reason": "earliest_quality_pass",
                "needs_review": False,
            },
        }
    ]
    return run, segments


def test_scene_slug_is_readable_unicode_and_path_safe() -> None:
    assert scene_slug("神奇 美景 / Guilin", "fallback") == "神奇-美景-Guilin"
    assert scene_slug("  ", "segment-0001") == "segment-0001"
    assert len(scene_slug("景" * 200, "fallback", 160).encode("utf-8")) <= 180


def test_annotation_writes_scene_named_image_and_three_indexes(tmp_path: Path) -> None:
    run, segments = _run(tmp_path)
    rows = render_frame_annotations(run, segments, FrameAnnotationConfig())
    assert len(rows) == 1
    row = rows[0]
    assert row["frame_timestamp"] == "00:00:12.345"
    assert row["source_frame_number_estimate"] == 370
    assert "神奇-美景-Guilin" in row["annotated_filename"]
    annotated = run / row["annotated_path"]
    assert annotated.is_file()
    assert Image.open(annotated).size == (240, 120)
    assert read_json(run / "frames/index.json")["frames"][0] == row
    with (run / "frames/index.csv").open(encoding="utf-8", newline="") as stream:
        csv_row = next(csv.DictReader(stream))
    assert csv_row["frame_timestamp"] == "00:00:12.345"
    markdown = (run / "frames/index.md").read_text(encoding="utf-8")
    assert "神奇 美景 / Guilin" in markdown
    assert "(annotated/" in markdown


def test_rerender_removes_stale_scene_filename(tmp_path: Path) -> None:
    run, segments = _run(tmp_path)
    first = render_frame_annotations(run, segments, FrameAnnotationConfig())[0]
    segments[0]["title"] = "Reviewed Scene"
    second = render_frame_annotations(run, segments, FrameAnnotationConfig())[0]
    assert not (run / first["annotated_path"]).exists()
    assert (run / second["annotated_path"]).exists()
    assert "Reviewed-Scene" in second["annotated_filename"]


def test_annotate_frames_command_retrofits_existing_run(tmp_path: Path) -> None:
    run, segments = _run(tmp_path)
    atomic_write_json(run / "config.json", asdict(Config()))
    atomic_write_json(run / "segments.json", {"segments": segments})
    assert main(["annotate-frames", str(run)]) == 0
    assert (run / "frames/index.json").is_file()
    assert len(list((run / "frames/annotated").glob("*.jpg"))) == 1
