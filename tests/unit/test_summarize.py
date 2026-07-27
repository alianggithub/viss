from vseg.config import SummaryConfig
from vseg.models import KeyPoint, SemanticSegment
from vseg.summarize import build_video_summary, render_video_summary


def _segment(index: int, title: str, points: list[str]) -> SemanticSegment:
    return SemanticSegment(
        id=f"segment-{index:04d}",
        start_s=float((index - 1) * 60),
        end_s=float(index * 60),
        type="topic",
        title=title,
        title_language="en",
        title_confidence=0.8,
        title_alternatives=[],
        key_points=[KeyPoint(text, [f"unit-{index}-{n}"], 0.7) for n, text in enumerate(points)],
        boundary_confidence=0.8,
        boundary_algorithm_version="test",
        boundary_evidence_refs=[],
        boundary_needs_review=False,
        transcript_segment_refs=[],
    )


def test_summary_is_transcript_grounded_balanced_and_deduplicated() -> None:
    segments = [
        _segment(1, "Alpha", ["First alpha fact", "Shared fact"]),
        _segment(2, "Beta", ["First beta fact", "Shared fact"]),
        _segment(3, "Gamma", ["First gamma fact", "Second gamma fact"]),
    ]
    result = build_video_summary(segments, SummaryConfig(max_key_points=5))
    assert result["provider"] == "vseg-transcript-extractive-v1"
    assert [item["text"] for item in result["key_points"]] == [
        "First alpha fact", "First beta fact", "First gamma fact", "Shared fact",
        "Second gamma fact",
    ]
    assert all(item["evidence_refs"] for item in result["key_points"])


def test_summary_renders_json_and_markdown(tmp_path) -> None:
    segments = [_segment(1, "Attraction", ["The transcript describes the entrance."])]
    result = render_video_summary(tmp_path, segments, SummaryConfig())
    assert result["key_point_count"] == 1
    assert (tmp_path / "summary.json").is_file()
    markdown = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "00:00:00" in markdown
    assert "The transcript describes the entrance." in markdown
