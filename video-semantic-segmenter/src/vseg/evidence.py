from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import av
import numpy as np
from PIL import Image

from .config import OcrConfig, VisualConfig
from .models import EvidenceEvent, Transcript


def _resize_gray(rgb: np.ndarray, width: int) -> np.ndarray:
    height = max(1, round(rgb.shape[0] * width / rgb.shape[1]))
    image = Image.fromarray(rgb).convert("L").resize((width, height), Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.float32) / 255.0


def detect_visual_events(path: Path, config: VisualConfig) -> list[EvidenceEvent]:
    """Stream compact visual metrics; persist no decoded source frames."""
    container = av.open(str(path))
    stream = container.streams.video[0]
    interval = 1.0 / config.sample_fps
    next_time = 0.0
    previous_histogram: np.ndarray | None = None
    events: list[EvidenceEvent] = []
    try:
        for frame in container.decode(stream):
            if frame.time is None or float(frame.time) + 1e-6 < next_time:
                continue
            timestamp = float(frame.time)
            next_time = timestamp + interval
            gray = _resize_gray(frame.to_ndarray(format="rgb24"), config.analysis_width)
            mean = float(gray.mean())
            histogram, _ = np.histogram(gray, bins=32, range=(0.0, 1.0), density=True)
            histogram = histogram / max(float(histogram.sum()), 1e-9)
            if mean <= config.black_threshold:
                events.append(
                    EvidenceEvent(
                        id=f"visual-black-{len(events)}",
                        timestamp_s=timestamp,
                        end_s=None,
                        source="visual",
                        kind="near_black",
                        score=1.0 - mean,
                        provider="vseg-histogram-v1",
                    )
                )
            if previous_histogram is not None:
                distance = float(np.abs(histogram - previous_histogram).sum() / 2.0)
                if distance >= config.cut_threshold:
                    events.append(
                        EvidenceEvent(
                            id=f"visual-cut-{len(events)}",
                            timestamp_s=timestamp,
                            end_s=None,
                            source="visual",
                            kind="hard_visual_cut",
                            score=min(1.0, distance),
                            provider="vseg-histogram-v1",
                            payload={"histogram_distance": round(distance, 5)},
                        )
                    )
            previous_histogram = histogram
    finally:
        container.close()
    return events


def transcript_gap_events(transcript: Transcript, threshold_s: float) -> list[EvidenceEvent]:
    events: list[EvidenceEvent] = []
    cursor = 0.0
    for segment in transcript.segments:
        gap = segment.start_s - cursor
        if gap >= threshold_s:
            events.append(
                EvidenceEvent(
                    id=f"transcript-gap-{len(events)}",
                    timestamp_s=cursor,
                    end_s=segment.start_s,
                    source="audio",
                    kind="long_transcript_gap",
                    score=min(1.0, gap / (threshold_s * 2.0)),
                    provider="vseg-gap-audit-v1",
                    payload={"duration_s": gap},
                )
            )
        cursor = max(cursor, segment.end_s)
    final_gap = transcript.duration_s - cursor
    if final_gap >= threshold_s:
        events.append(
            EvidenceEvent(
                id=f"transcript-gap-{len(events)}",
                timestamp_s=cursor,
                end_s=transcript.duration_s,
                source="audio",
                kind="long_transcript_gap",
                score=min(1.0, final_gap / (threshold_s * 2.0)),
                provider="vseg-gap-audit-v1",
                payload={"duration_s": final_gap},
            )
        )
    return events


def extract_frame(path: Path, timestamp_s: float) -> tuple[float, np.ndarray]:
    container = av.open(str(path))
    stream = container.streams.video[0]
    try:
        container.seek(int(max(0.0, timestamp_s - 1.0) * av.time_base), backward=True)
        for frame in container.decode(stream):
            if frame.time is not None and float(frame.time) >= timestamp_s:
                return float(frame.time), frame.to_ndarray(format="bgr24")
    finally:
        container.close()
    raise RuntimeError(f"no frame at or after {timestamp_s:.3f}s")


class RapidOcrProvider:
    def __init__(self, config: OcrConfig, engine: Any = None) -> None:
        self.config = config
        self._engine = engine

    @property
    def provider_version(self) -> str:
        try:
            import rapidocr

            return f"rapidocr/{rapidocr.__version__}"
        except (ImportError, AttributeError):
            return "rapidocr:unknown"

    def _load(self) -> Any:
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr import RapidOCR
        except ImportError as exc:
            raise RuntimeError(
                "RapidOCR is not installed; install the 'ocr' or 'all' extra"
            ) from exc
        self._engine = RapidOCR()
        return self._engine

    def recognize_at(self, media_path: Path, timestamps: Iterable[float]) -> list[EvidenceEvent]:
        if self.config.mode == "off":
            return []
        engine = self._load()
        events: list[EvidenceEvent] = []
        seen: set[str] = set()
        for requested in timestamps:
            actual, image = extract_frame(media_path, requested)
            result = engine(image)
            texts = getattr(result, "txts", ()) if result else ()
            scores = getattr(result, "scores", ()) if result else ()
            boxes = getattr(result, "boxes", ()) if result else ()
            for index, text in enumerate(texts):
                normalized = "".join(str(text).split())
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                score = float(scores[index]) if index < len(scores) else None
                box = boxes[index].tolist() if index < len(boxes) else None
                events.append(
                    EvidenceEvent(
                        id=f"ocr-{len(events)}",
                        timestamp_s=actual,
                        end_s=None,
                        source="ocr",
                        kind="recognized_text",
                        score=score,
                        provider=self.provider_version,
                        payload={"text": str(text), "box": box},
                    )
                )
        return events


def interval_has_visual_activity(
    event: EvidenceEvent, visual_events: list[EvidenceEvent], margin_s: float = 0.5
) -> bool:
    end = event.end_s if event.end_s is not None else event.timestamp_s
    return any(
        event.timestamp_s - margin_s <= item.timestamp_s <= end + margin_s for item in visual_events
    )


def finite_score(value: float | None, default: float = 0.0) -> float:
    return default if value is None or not math.isfinite(value) else max(0.0, min(1.0, value))
