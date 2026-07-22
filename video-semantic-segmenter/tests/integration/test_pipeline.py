from __future__ import annotations

import hashlib
import csv
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from vseg.config import Config
from vseg.models import EvidenceEvent, Transcript, TranscriptSegment, TranscriptWord
from vseg.pipeline import analyze
from vseg.review import record_override
from vseg.validate import validate_run


def _video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("mpeg4", rate=10)
    stream.width = 160
    stream.height = 96
    stream.pix_fmt = "yuv420p"
    colors = [(190, 40, 40), (40, 190, 40), (40, 40, 190)]
    for index in range(36):
        image = np.empty((96, 160, 3), dtype=np.uint8)
        image[:] = colors[min(2, index // 12)]
        image[:, index % 150 : index % 150 + 10] = 255
        frame = av.VideoFrame.from_ndarray(image, format="rgb24")
        frame.pts = index
        frame.time_base = Fraction(1, 10)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


class FakeTranscriber:
    provider_version = "fake-asr/1"

    def transcribe(self, media_path, clip=None, vad=None, provenance="primary_asr"):
        phrases = ["Visit Alpha.", "Visit Beta.", "Visit Gamma."]
        starts = [0.0, 1.2, 2.4]
        segments = []
        for index, (text, start) in enumerate(zip(phrases, starts, strict=True)):
            word = TranscriptWord(f"w{index}", start, start + 0.7, text, 0.99)
            segments.append(
                TranscriptSegment(
                    f"s{index}", start, start + 0.7, text, [word], provenance=provenance
                )
            )
        return Transcript("en", 0.99, 3.6, self.provider_version, segments)


class FakeOcr:
    def recognize_at(self, media_path, timestamps):
        return [
            EvidenceEvent(
                f"o{i}",
                stamp,
                None,
                "ocr",
                "recognized_text",
                0.9,
                "fake-ocr",
                {"text": f"Title {i + 1}"},
            )
            for i, stamp in enumerate(timestamps)
        ]


def test_pipeline_produces_valid_deliverables(tmp_path: Path) -> None:
    source = tmp_path / "input.mp4"
    run = tmp_path / "run"
    _video(source)
    config = Config()
    config.semantic.candidate_merge_s = 0.25
    config.semantic.pause_threshold_s = 0.9
    config.transcription.suspicious_gap_s = 10.0
    config.visual.sample_fps = 2.0
    analyze(source, run, config, transcriber=FakeTranscriber(), ocr_provider=FakeOcr())
    assert validate_run(run) == []
    assert len(list((run / "frames").glob("*.jpg"))) == 3
    annotated = list((run / "frames/annotated").glob("*.jpg"))
    assert len(annotated) == 3
    assert all("__00-00-" in path.name for path in annotated)
    with (run / "frames/index.csv").open(encoding="utf-8", newline="") as stream:
        frame_rows = list(csv.DictReader(stream))
    assert len(frame_rows) == 3
    assert {row["frame_timestamp"] for row in frame_rows}
    assert "Title 1" in (run / "chapters.md").read_text(encoding="utf-8")
    for relative in (
        "config.effective.yaml",
        "segments.raw.json",
        "transcript/transcript.md",
        "evidence/audio-events.json",
        "evidence/visual-events.json",
        "evidence/ocr-events.json",
        "evidence/boundary-candidates.json",
        "logs/run.jsonl",
    ):
        assert (run / relative).is_file()

    protected = [run / "transcript/transcript.json", run / "evidence/boundary-candidates.json"]
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in protected]
    record_override(run, "segment-0002", title="Reviewed Beta", reviewer="tester", verified=True)
    after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in protected]
    assert before == after
    assert "Reviewed Beta" in (run / "chapters.md").read_text(encoding="utf-8")
    assert any("Reviewed-Beta" in path.name for path in (run / "frames/annotated").glob("*.jpg"))

    analyze(
        source,
        run,
        config,
        resume=True,
        transcriber=FakeTranscriber(),
        ocr_provider=FakeOcr(),
    )
    assert "Reviewed Beta" in (run / "chapters.md").read_text(encoding="utf-8")
    assert validate_run(run) == []
