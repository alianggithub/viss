from __future__ import annotations

from pathlib import Path

import av
import numpy as np
from PIL import Image

from .config import FrameSelectionConfig
from .models import FrameDecision, SemanticSegment


def frame_quality(bgr: np.ndarray) -> tuple[float, dict[str, float]]:
    """Estimate whether a frame is visible, sharp, and visually informative."""
    rgb = bgr[:, :, ::-1]
    gray = np.asarray(Image.fromarray(rgb).convert("L"), dtype=np.float32) / 255.0
    brightness = float(gray.mean())
    contrast = float(gray.std())
    gy, gx = np.gradient(gray)
    sharpness = float(np.sqrt(gx * gx + gy * gy).mean())
    exposure = max(0.0, 1.0 - abs(brightness - 0.5) / 0.5)
    contrast_score = min(1.0, contrast / 0.22)
    sharpness_score = min(1.0, sharpness / 0.08)
    quality = 0.38 * exposure + 0.28 * contrast_score + 0.34 * sharpness_score
    return quality, {
        "brightness": round(brightness, 5),
        "contrast": round(contrast, 5),
        "sharpness": round(sharpness, 5),
    }


def select_representative_frame(
    media_path: Path,
    segment: SemanticSegment,
    frames_dir: Path,
    config: FrameSelectionConfig,
) -> FrameDecision:
    """Choose the earliest acceptable frame, falling back to best quality."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    search_end = min(segment.end_s, segment.start_s + config.search_window_s)
    interval = 1.0 / config.sample_fps
    candidates: list[tuple[float, float, np.ndarray, dict[str, float]]] = []
    container = av.open(str(media_path))
    stream = container.streams.video[0]
    next_sample = segment.start_s
    try:
        container.seek(int(max(0.0, segment.start_s - 1.0) * av.time_base), backward=True)
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            actual = float(frame.time)
            if actual + 1e-6 < next_sample:
                continue
            if actual >= search_end + 1e-3:
                break
            bgr = frame.to_ndarray(format="bgr24")
            quality, metrics = frame_quality(bgr)
            candidates.append((actual, quality, bgr, metrics))
            next_sample = actual + interval
            if quality >= config.min_quality:
                break
    finally:
        container.close()
    if not candidates:
        raise RuntimeError(f"no representative-frame candidates for {segment.id}")
    acceptable = next((item for item in candidates if item[1] >= config.min_quality), None)
    selected = acceptable or max(candidates, key=lambda item: item[1])
    actual, quality, bgr, _ = selected
    relative = f"frames/{segment.id}.jpg"
    Image.fromarray(bgr[:, :, ::-1]).save(frames_dir / f"{segment.id}.jpg", quality=90)
    return FrameDecision(
        path=relative,
        timestamp_s=actual,
        quality_score=quality,
        relevance_score=None,
        selection_reason="earliest_quality_pass" if acceptable else "best_quality_fallback",
        needs_review=quality < config.min_quality,
        candidate_scores=[
            {"timestamp_s": timestamp, "quality_score": score, **metrics}
            for timestamp, score, _, metrics in candidates
        ],
    )
