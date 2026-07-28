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
    atomic_write_json(run / "source.json", {"duration_s": 60.0, "average_fps": 30.0})
    segments = [
        {
            "id": "segment-0001", "start_s": 10.0, "end_s": 30.0,
            "title": "神奇 美景 / Guilin",
            "representative_frame": {
                "path": "frames/segment-0001.jpg", "timestamp_s": 12.345,
                "quality_score": 0.91, "selection_reason": "earliest_quality_pass",
                "needs_review": False,
            },
        }
    ]
    return run, segments


def test_scene_slug_is_readable_unicode_and_path_safe() -> None:
    assert scene_slug("神奇 美景 / Guilin", "fallback") == "神奇-美景-Guilin"
    assert scene_slug("  ", "segment-0001") == "segment-0001"
    assert len(scene_slug("景" * 200, "fallback", 160).encode("utf-8")) <= 180


def test_annotation_overwrites_canonical_frame_and_writes_three_indexes(tmp_path: Path) -> None:
    run, segments = _run(tmp_path)
    before = (run / "frames/segment-0001.jpg").read_bytes()
    rows = render_frame_annotations(run, segments, FrameAnnotationConfig())
    assert len(rows) == 1
    row = rows[0]
    assert row["frame_timestamp"] == "00:00:12.345"
    assert row["source_frame_number_estimate"] == 370
    # Frame should be renamed to scene-aware filename
    assert row["frame_path"] == "frames/segment-0001.jpg"
    assert row["annotated_filename"].startswith("0001__00-00-12-345__")
    assert "神奇-美景-Guilin" in row["annotated_filename"]
    # Original file should be replaced by annotated version with new name
    assert not (run / "frames/segment-0001.jpg").exists()
    assert (run / row["frame_path"]).parent.joinpath(row["annotated_filename"]).exists()
    assert (run / row["frame_path"]).parent.joinpath(row["annotated_filename"]).read_bytes() != before
    assert not (run / "frames/annotated").exists()
    assert read_json(run / "frames/index.json")["output_mode"] == "annotated_only"
    with (run / "frames/index.csv").open(encoding="utf-8", newline="") as stream:
        csv_row = next(csv.DictReader(stream))
    assert csv_row["frame_timestamp"] == "00:00:12.345"
    markdown = (run / "frames/index.md").read_text(encoding="utf-8")
    assert "神奇 美景 / Guilin" in markdown
    assert f"({row['annotated_filename']})" in markdown


def test_rerender_keeps_one_stable_annotated_frame(tmp_path: Path) -> None:
    run, segments = _run(tmp_path)
    render_frame_annotations(run, segments, FrameAnnotationConfig())
    segments[0]["title"] = "Reviewed Scene"
    row = render_frame_annotations(run, segments, FrameAnnotationConfig())[0]
    assert (run / row["frame_path"]).parent.joinpath(row["annotated_filename"]).is_file()
    assert len(list((run / "frames").glob("*.jpg"))) == 1
    assert not (run / "frames/annotated").exists()
    assert "Reviewed Scene" in (run / "frames/index.md").read_text(encoding="utf-8")


def test_annotate_frames_command_retrofits_existing_run(tmp_path: Path) -> None:
    run, segments = _run(tmp_path)
    legacy = run / "frames" / "annotated"
    legacy.mkdir()
    Image.open(run / "frames/segment-0001.jpg").save(legacy / "old.jpg")
    atomic_write_json(run / "config.json", asdict(Config()))
    atomic_write_json(run / "segments.json", {"segments": segments})
    assert main(["annotate-frames", str(run)]) == 0
    assert (run / "frames/index.json").is_file()
    # Should have exactly one frame file (scene-aware named)
    frame_files = list((run / "frames").glob("*.jpg"))
    assert len(frame_files) == 1
    assert not legacy.exists()
