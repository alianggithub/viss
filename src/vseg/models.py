from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceMetadata:
    path: str
    sha256: str
    duration_s: float
    format_name: str
    video_codec: str
    width: int
    height: int
    average_fps: float | None
    video_time_base: str
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    chapters: list[dict[str, Any]] = field(default_factory=list)
    subtitle_streams: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TranscriptWord:
    id: str
    start_s: float
    end_s: float
    text: str
    probability: float | None = None


@dataclass(slots=True)
class TranscriptSegment:
    id: str
    start_s: float
    end_s: float
    text: str
    words: list[TranscriptWord] = field(default_factory=list)
    confidence: float | None = None
    no_speech_probability: float | None = None
    provenance: str = "primary_asr"


@dataclass(slots=True)
class Transcript:
    language: str
    language_probability: float | None
    duration_s: float
    provider: str
    segments: list[TranscriptSegment]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvidenceEvent:
    id: str
    timestamp_s: float
    end_s: float | None
    source: str
    kind: str
    score: float | None
    provider: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BoundaryCandidate:
    id: str
    timestamp_s: float
    source: str
    kind: str
    raw_score: float
    normalized_score: float
    provider: str
    evidence_refs: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    cluster_id: str | None = None


@dataclass(slots=True)
class KeyPoint:
    text: str
    evidence_refs: list[str]
    confidence: float | None


@dataclass(slots=True)
class FrameDecision:
    path: str
    timestamp_s: float
    quality_score: float
    relevance_score: float | None
    selection_reason: str
    needs_review: bool
    candidate_scores: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class SemanticSegment:
    id: str
    start_s: float
    end_s: float
    type: str
    title: str
    title_language: str
    title_confidence: float | None
    title_alternatives: list[str]
    key_points: list[KeyPoint]
    boundary_confidence: float | None
    boundary_algorithm_version: str
    boundary_evidence_refs: list[str]
    boundary_needs_review: bool
    transcript_segment_refs: list[str]
    representative_frame: FrameDecision | None = None


def jsonable(value: Any) -> Any:
    """Convert dataclass trees into JSON-compatible Python values."""
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value
