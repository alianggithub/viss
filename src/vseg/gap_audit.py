from __future__ import annotations

from pathlib import Path

from .evidence import interval_has_visual_activity, transcript_gap_events
from .models import EvidenceEvent, Transcript
from .transcribe import FasterWhisperTranscriber, merge_transcripts


def suspicious_gaps(
    transcript: Transcript,
    visual_events: list[EvidenceEvent],
    threshold_s: float,
) -> list[EvidenceEvent]:
    """Return transcript gaps that are likely to contain useful video content."""
    gaps = transcript_gap_events(transcript, threshold_s)
    if not visual_events:
        return gaps
    return [gap for gap in gaps if interval_has_visual_activity(gap, visual_events)]


def recover_suspicious_gaps(
    media_path: Path,
    transcript: Transcript,
    visual_events: list[EvidenceEvent],
    transcriber: FasterWhisperTranscriber,
    threshold_s: float,
    margin_s: float = 1.0,
) -> tuple[Transcript, list[EvidenceEvent]]:
    """Re-run ASR without VAD over suspicious gaps and merge useful results."""
    gaps = suspicious_gaps(transcript, visual_events, threshold_s)
    recovered: list[Transcript] = []
    for gap in gaps:
        end_s = gap.end_s if gap.end_s is not None else gap.timestamp_s
        clip = (
            max(0.0, gap.timestamp_s - margin_s),
            min(transcript.duration_s, end_s + margin_s),
        )
        result = transcriber.transcribe(
            media_path,
            clip=clip,
            vad=False,
            provenance=f"gap_recovery_{len(recovered)}",
        )
        if result.segments:
            recovered.append(result)
            gap.payload["recovered_segment_count"] = len(result.segments)
            gap.payload["recovery_status"] = "recovered"
        else:
            gap.payload["recovery_status"] = "no_speech_found"
    return merge_transcripts(transcript, recovered), gaps
