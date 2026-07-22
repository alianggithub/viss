from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import av

from .io import sha256_file
from .models import SourceMetadata


class MediaProbeError(RuntimeError):
    pass


def _seconds(value: int | None, time_base: Fraction | None) -> float | None:
    if value is None or time_base is None:
        return None
    return float(value * time_base)


def probe_media(path: Path) -> SourceMetadata:
    if not path.is_file():
        raise MediaProbeError(f"source is not a readable regular file: {path}")
    try:
        container = av.open(str(path))
    except Exception as exc:
        raise MediaProbeError(f"cannot open media: {exc}") from exc
    try:
        if not container.streams.video:
            raise MediaProbeError("source has no video stream")
        video = container.streams.video[0]
        duration_s = (
            float(container.duration / av.time_base)
            if container.duration is not None
            else (_seconds(video.duration, video.time_base) or 0.0)
        )
        if duration_s <= 0:
            raise MediaProbeError("source has zero or unknown duration")
        audio = container.streams.audio[0] if container.streams.audio else None
        subtitles = [
            {
                "index": stream.index,
                "codec": stream.codec_context.name,
                "language": stream.metadata.get("language"),
            }
            for stream in container.streams.subtitles
        ]
        chapters: list[dict[str, Any]] = []
        chapter_source = getattr(container, "chapters", [])
        if callable(chapter_source):
            chapter_source = chapter_source()
        for index, chapter in enumerate(chapter_source or []):
            chapters.append(
                {
                    "id": str(getattr(chapter, "id", index)),
                    "start_s": _seconds(chapter.start, chapter.time_base),
                    "end_s": _seconds(chapter.end, chapter.time_base),
                    "title": getattr(chapter, "metadata", {}).get("title"),
                }
            )
        rate = float(video.average_rate) if video.average_rate else None
        return SourceMetadata(
            path=str(path.resolve()),
            sha256=sha256_file(path),
            duration_s=duration_s,
            format_name=container.format.name,
            video_codec=video.codec_context.name,
            width=video.codec_context.width,
            height=video.codec_context.height,
            average_fps=rate,
            video_time_base=str(video.time_base),
            audio_codec=audio.codec_context.name if audio else None,
            audio_sample_rate=audio.codec_context.sample_rate if audio else None,
            chapters=chapters,
            subtitle_streams=subtitles,
        )
    finally:
        container.close()
