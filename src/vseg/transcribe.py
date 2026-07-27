from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import TranscriptionConfig
from .models import Transcript, TranscriptSegment, TranscriptWord


class TranscriptionError(RuntimeError):
    pass


@dataclass(slots=True)
class FasterWhisperTranscriber:
    config: TranscriptionConfig
    device: str = "cpu"
    download_root: Path | None = None
    local_files_only: bool = True
    _model: Any = None

    @property
    def provider_version(self) -> str:
        try:
            import faster_whisper

            return f"faster-whisper/{faster_whisper.__version__}:{self.config.model}"
        except (ImportError, AttributeError):
            return f"faster-whisper:unknown:{self.config.model}"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed; install the 'asr' or 'all' extra"
            ) from exc
        kwargs: dict[str, Any] = {
            "device": self.device,
            "compute_type": "int8" if self.device == "cpu" else "float16",
            "cpu_threads": self.config.cpu_threads,
        }
        if self.download_root:
            kwargs["download_root"] = str(self.download_root)
        kwargs["local_files_only"] = self.local_files_only
        self._model = WhisperModel(self.config.model, **kwargs)
        return self._model

    def transcribe(
        self,
        media_path: Path,
        clip: tuple[float, float] | None = None,
        vad: bool | None = None,
        provenance: str = "primary_asr",
    ) -> Transcript:
        model = self._load_model()
        language = None if self.config.language == "auto" else self.config.language
        clip_timestamps = "0" if clip is None else f"{clip[0]},{clip[1]}"
        use_vad = self.config.vad if vad is None else vad
        try:
            iterator, info = model.transcribe(
                str(media_path),
                language=language,
                beam_size=5,
                word_timestamps=self.config.word_timestamps,
                vad_filter=use_vad,
                vad_parameters={"min_silence_duration_ms": 500} if use_vad else None,
                clip_timestamps=clip_timestamps,
                condition_on_previous_text=True,
            )
            segments = list(_convert_segments(iterator, provenance))
        except Exception as exc:
            raise TranscriptionError(f"transcription failed: {exc}") from exc
        return Transcript(
            language=info.language,
            language_probability=getattr(info, "language_probability", None),
            duration_s=float(info.duration),
            provider=self.provider_version,
            segments=segments,
        )


def _convert_segments(iterator: Iterable[Any], provenance: str) -> Iterable[TranscriptSegment]:
    for segment in iterator:
        words = [
            TranscriptWord(
                id=f"word-{segment.id}-{index}",
                start_s=float(word.start),
                end_s=float(word.end),
                text=word.word,
                probability=getattr(word, "probability", None),
            )
            for index, word in enumerate(segment.words or [])
            if word.start is not None and word.end is not None
        ]
        confidence = None
        if getattr(segment, "avg_logprob", None) is not None:
            confidence = max(0.0, min(1.0, 1.0 + float(segment.avg_logprob)))
        yield TranscriptSegment(
            id=f"asr-{provenance}-{segment.id}",
            start_s=float(segment.start),
            end_s=float(segment.end),
            text=segment.text.strip(),
            words=words,
            confidence=confidence,
            no_speech_probability=getattr(segment, "no_speech_prob", None),
            provenance=provenance,
        )


def transcript_from_dict(value: dict[str, Any]) -> Transcript:
    segments = []
    for item in value["segments"]:
        words = [TranscriptWord(**word) for word in item.get("words", [])]
        segments.append(TranscriptSegment(**{**item, "words": words}))
    return Transcript(**{**value, "segments": segments})


def merge_transcripts(primary: Transcript, recovered: list[Transcript]) -> Transcript:
    """Merge interval passes while avoiding duplicate overlapping primary segments."""
    additions = [segment for transcript in recovered for segment in transcript.segments]
    if not additions:
        return primary
    retained = []
    for segment in primary.segments:
        overlap = any(
            min(segment.end_s, item.end_s) - max(segment.start_s, item.start_s)
            > 0.6 * min(segment.end_s - segment.start_s, item.end_s - item.start_s)
            for item in additions
        )
        if not overlap:
            retained.append(segment)
    merged = sorted(retained + additions, key=lambda item: (item.start_s, item.end_s))
    return Transcript(
        language=primary.language,
        language_probability=primary.language_probability,
        duration_s=primary.duration_s,
        provider=primary.provider,
        segments=merged,
        warnings=primary.warnings,
    )
