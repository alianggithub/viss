from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from vseg.cli import main
from vseg.config import UserFrameDumpConfig
from vseg.io import read_json
from vseg.user_frames import _Candidate, _choose_candidate, load_timestamp_requests, parse_timestamp


def _video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=10)
    stream.width = 160
    stream.height = 96
    stream.pix_fmt = "yuv420p"
    for index in range(30):
        yy, xx = np.indices((96, 160))
        image = np.empty((96, 160, 3), dtype=np.uint8)
        image[:, :, 0] = (xx * 3 + index * 7) % 255
        image[:, :, 1] = (yy * 5 + index * 11) % 255
        image[:, :, 2] = ((xx + yy) * 2 + index * 13) % 255
        frame = av.VideoFrame.from_ndarray(image, format="rgb24")
        frame.pts = index
        frame.time_base = Fraction(1, 10)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def _candidate(stamp: float, quality: float, proximity: float, score: float) -> _Candidate:
    return _Candidate(
        timestamp_s=stamp,
        frame_number=None,
        image=np.zeros((2, 2, 3), dtype=np.uint8),
        quality_score=quality,
        metrics={},
        proximity_score=proximity,
        selection_score=score,
    )


@pytest.mark.parametrize(
    ("value", "expected"), [("83", 83.0), ("01:23", 83.0), ("1:02:03", 3723.0)]
)
def test_parse_timestamp_formats(value: str, expected: float) -> None:
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", ["", "1.5", "1:60", "1:2:60", "noon", "-1"])
def test_parse_timestamp_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_timestamp(value)


def test_timestamp_file_supports_comments_labels_and_line_errors(tmp_path: Path) -> None:
    source = tmp_path / "timestamps.txt"
    source.write_text("# chosen scenes\n00:01 | Entrance\n\n65 | Lake\n", encoding="utf-8")
    requests = load_timestamp_requests([], source)
    assert [(item.timestamp_s, item.label, item.source_line) for item in requests] == [
        (1.0, "Entrance", 2), (65.0, "Lake", 4)
    ]
    source.write_text("00:01\nbad\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"timestamps.txt:2"):
        load_timestamp_requests([], source)


def test_fine_tuning_can_prefer_clear_nearby_frame() -> None:
    candidates = [_candidate(10.0, 0.2, 1.0, 0.36), _candidate(10.4, 0.9, 0.6, 0.84)]
    assert _choose_candidate(candidates, 10.0, UserFrameDumpConfig()).timestamp_s == 10.4
    assert _choose_candidate(
        candidates, 10.0, UserFrameDumpConfig(fine_tune=False)
    ).timestamp_s == 10.0


def test_dump_frames_writes_only_annotated_images_and_three_indexes(tmp_path: Path) -> None:
    source = tmp_path / "input.mp4"
    output = tmp_path / "dump"
    request_file = tmp_path / "timestamps.txt"
    _video(source)
    request_file.write_text("00:00 | Opening\n00:01 | Main scene\n", encoding="utf-8")
    assert main(
        [
            "dump-frames", str(source), "--timestamps-file", str(request_file),
            "--timestamp", "2|Closing", "--output", str(output),
        ]
    ) == 0
    manifest = read_json(output / "index.json")
    assert manifest["schema_version"] == "1.1"
    assert manifest["output_mode"] == "annotated_only"
    assert manifest["frame_count"] == 3
    assert [item["label"] for item in manifest["frames"]] == ["Closing", "Opening", "Main scene"]
    assert not (output / "annotated").exists()
    assert len(list((output / "frames").glob("*.jpg"))) == 3
    for row in manifest["frames"]:
        assert abs(row["offset_s"]) <= 1.001
        assert (output / row["frame_path"]).is_file()
        assert "raw_path" not in row
        assert "annotated_path" not in row
        assert row["candidate_count"] > 0
    assert (output / "index.csv").is_file()
    assert "Main scene" in (output / "index.md").read_text(encoding="utf-8")


def test_default_dump_output_is_beside_source_video(tmp_path: Path) -> None:
    source = tmp_path / "my-trip.mp4"
    _video(source)
    assert main(["dump-frames", str(source), "--timestamp", "1|View"]) == 0
    output = tmp_path / "my-trip-timestamp-frames"
    assert (output / "index.json").is_file()
    assert len(list((output / "frames").glob("*.jpg"))) == 1


def test_raw_and_annotated_compatibility_mode(tmp_path: Path) -> None:
    source = tmp_path / "input.mp4"
    output = tmp_path / "dump"
    _video(source)
    assert main(
        [
            "dump-frames", str(source), "--timestamp", "1|View", "--output", str(output),
            "--raw-and-annotated",
        ]
    ) == 0
    row = read_json(output / "index.json")["frames"][0]
    assert (output / row["raw_path"]).is_file()
    assert (output / row["annotated_path"]).is_file()


def test_dump_frames_rejects_all_requests_before_writing(tmp_path: Path, capsys) -> None:
    source = tmp_path / "input.mp4"
    output = tmp_path / "dump"
    _video(source)
    assert main(["dump-frames", str(source), "--timestamp", "99", "--output", str(output)]) == 2
    assert "beyond video duration" in capsys.readouterr().err
    assert not (output / "index.json").exists()
