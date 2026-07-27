from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vseg.config import VisionRecognitionConfig
from vseg.models import FrameDecision, SemanticSegment
from vseg.vision import VisionResult, _parse_response, recognize_segment_frames, render_visual_descriptions


class FakeRecognizer:
    def __init__(self, available: bool = True):
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def recognize(self, image_path: Path, prompt: str) -> VisionResult:
        assert image_path.is_file()
        assert "transcript topic" in prompt
        return VisionResult("A mountain lake is visible.", 0.91, "fake-vl", "{}")


def _segment(run_dir: Path) -> SemanticSegment:
    (run_dir / "frames").mkdir(parents=True)
    Image.fromarray(np.full((20, 30, 3), 120, dtype=np.uint8)).save(
        run_dir / "frames" / "segment-0001.jpg"
    )
    return SemanticSegment(
        id="segment-0001", start_s=0, end_s=10, type="topic", title="Mountain lake",
        title_language="en", title_confidence=0.8, title_alternatives=[], key_points=[],
        boundary_confidence=0.8, boundary_algorithm_version="test", boundary_evidence_refs=[],
        boundary_needs_review=False, transcript_segment_refs=[],
        representative_frame=FrameDecision(
            path="frames/segment-0001.jpg", timestamp_s=1.2, quality_score=0.8,
            relevance_score=None, selection_reason="test", needs_review=False,
        ),
    )


def test_vision_response_json_and_text_parsing() -> None:
    parsed = _parse_response('```json\n{"description":"A bridge", "relevance_score":1.4}\n```')
    assert parsed == {"description": "A bridge", "relevance_score": 1.0}
    assert _parse_response("A plain description.")["description"] == "A plain description."


def test_auto_mode_recognizes_and_records_grounded_event(tmp_path: Path) -> None:
    segment = _segment(tmp_path)
    events, warnings = recognize_segment_frames(
        tmp_path, [segment], VisionRecognitionConfig(), FakeRecognizer()
    )
    assert warnings == []
    assert events[0].payload["description"] == "A mountain lake is visible."
    assert events[0].provider.endswith("fake-vl")
    assert segment.representative_frame.relevance_score == 0.91
    render_visual_descriptions(tmp_path, events)
    assert "mountain lake" in (tmp_path / "visual-descriptions.md").read_text().lower()


def test_auto_mode_warns_but_on_mode_requires_available_server(tmp_path: Path) -> None:
    segment = _segment(tmp_path)
    events, warnings = recognize_segment_frames(
        tmp_path, [segment], VisionRecognitionConfig(mode="auto"), FakeRecognizer(False)
    )
    assert events == []
    assert "vision model unavailable" in warnings[0]
    with pytest.raises(RuntimeError, match="vision model unavailable"):
        recognize_segment_frames(
            tmp_path, [segment], VisionRecognitionConfig(mode="on"), FakeRecognizer(False)
        )
