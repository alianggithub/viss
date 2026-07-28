from __future__ import annotations

import hashlib
import json
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .checkpoints import CheckpointStore
from .config import Config
from .evidence import RapidOcrProvider, detect_visual_events
from .frame_annotations import render_frame_annotations
from .frames import select_representative_frame
from .gap_audit import recover_suspicious_gaps
from .io import atomic_write_json, read_json, sha256_file
from .models import EvidenceEvent, SourceMetadata, jsonable
from .probe import probe_media
from .render import render_report, render_segments, render_transcript
from .semantic import build_segments, event_candidates, fuse_candidates, semantic_candidates
from .summarize import render_video_summary
from .transcribe import FasterWhisperTranscriber, transcript_from_dict
from .validate import validate_run
from .vision import OpenAICompatibleVisionRecognizer, recognize_segment_frames, render_visual_descriptions
from .organize import post_analysis_organize

Progress = Callable[[str], None]


def _default_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _evidence_from_dict(item: dict[str, Any]) -> EvidenceEvent:
    return EvidenceEvent(**item)


def _stage_hash(source_hash: str, name: str) -> str:
    return hashlib.sha256(f"{source_hash}:{name}".encode()).hexdigest()


def _write_evidence(run_dir: Path, name: str, values: list[Any]) -> Path:
    path = run_dir / "evidence" / f"{name}.json"
    atomic_write_json(path, jsonable(values))
    return path


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _log(run_dir: Path, stage: str, message: str) -> None:
    directory = run_dir / "logs"
    directory.mkdir(exist_ok=True)
    with (directory / "run.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"timestamp": _now(), "stage": stage, "message": message}) + "\n")


def analyze(
    media_path: Path,
    run_dir: Path,
    config: Config,
    *,
    resume: bool = False,
    progress: Progress = _default_progress,
    transcriber: FasterWhisperTranscriber | None = None,
    ocr_provider: RapidOcrProvider | None = None,
    vision_recognizer: OpenAICompatibleVisionRecognizer | None = None,
    title_override: str | None = None,
) -> Path:
    media_path = media_path.expanduser().resolve()
    run_dir = run_dir.expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()) and not resume:
        raise FileExistsError(f"output directory is not empty: {run_dir}; use resume")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(exist_ok=True)
    checkpoint = CheckpointStore(run_dir)
    warnings: list[str] = []
    existing_run = read_json(run_dir / "run.json") if resume and (run_dir / "run.json").exists() else {}
    created_at = existing_run.get("created_at", _now())

    progress("[1/9] Probing source media")
    source_path = run_dir / "source.json"
    if resume and source_path.exists():
        source = SourceMetadata(**read_json(source_path))
        if Path(source.path) != media_path:
            raise ValueError("resume source path does not match recorded source")
    else:
        source = probe_media(media_path)
        atomic_write_json(source_path, jsonable(source))
    atomic_write_json(run_dir / "config.json", asdict(config))
    (run_dir / "config.effective.yaml").write_text(
        yaml.safe_dump(asdict(config), sort_keys=True, allow_unicode=True), encoding="utf-8"
    )
    config_hash = config.sha256()
    run_id = existing_run.get("run_id", str(uuid.uuid4()))
    atomic_write_json(
        run_dir / "run.json",
        {
            "schema_version": "1.0",
            "run_id": run_id,
            "source_sha256": source.sha256,
            "config_sha256": config_hash,
            "status": "running",
            "created_at": created_at,
            "updated_at": _now(),
            "completed_stages": ["probe"],
            "warnings": warnings,
            "software_versions": {"vseg": "0.4.0", "media": "PyAV"},
        },
    )
    _log(run_dir, "probe", "source probe complete")
    checkpoint.save("probe", "complete", source.sha256, config_hash, "pyav", {"path": "source.json"})

    progress("[2/9] Transcribing speech with word timestamps")
    transcript_path = run_dir / "transcript" / "transcript.json"
    if resume and transcript_path.exists():
        transcript = transcript_from_dict(read_json(transcript_path))
        transcriber = transcriber or FasterWhisperTranscriber(
            config.transcription,
            device="cpu" if config.runtime.device == "auto" else config.runtime.device,
            download_root=run_dir / "models" if config.privacy.allow_network_models else None,
            local_files_only=not config.privacy.allow_network_models,
        )
    else:
        transcriber = transcriber or FasterWhisperTranscriber(
            config.transcription,
            device="cpu" if config.runtime.device == "auto" else config.runtime.device,
            download_root=run_dir / "models" if config.privacy.allow_network_models else None,
            local_files_only=not config.privacy.allow_network_models,
        )
        transcript = transcriber.transcribe(media_path)

    progress("[3/9] Measuring visual transitions")
    visual_path = run_dir / "evidence" / "visual-events.json"
    if resume and visual_path.exists():
        visual_events = [_evidence_from_dict(item) for item in read_json(visual_path)]
    else:
        visual_events = detect_visual_events(media_path, config.visual)
        _write_evidence(run_dir, "visual-events", visual_events)

    progress("[4/9] Auditing transcript gaps")
    if not (resume and transcript_path.exists()):
        transcript, gap_events = recover_suspicious_gaps(
            media_path,
            transcript,
            visual_events,
            transcriber,
            config.transcription.suspicious_gap_s,
        )
        _write_evidence(run_dir, "audio-events", gap_events)
        render_transcript(run_dir, transcript)
    elif not (run_dir / "evidence" / "audio-events.json").exists():
        _write_evidence(run_dir, "audio-events", [])
    checkpoint.save(
        "transcript",
        "complete",
        source.sha256,
        config_hash,
        transcript.provider,
        {"path": "transcript/transcript.json"},
    )

    progress("[5/9] Discovering semantic boundary candidates")
    semantic, units = semantic_candidates(transcript, config.semantic)
    chapter_events = [
        EvidenceEvent(
            id=f"chapter-{index}",
            timestamp_s=float(chapter["start_s"] or 0.0),
            end_s=chapter.get("end_s"),
            source="chapter",
            kind="embedded_chapter",
            score=1.0,
            provider="media-container",
            payload={"title": chapter.get("title")},
        )
        for index, chapter in enumerate(source.chapters)
    ]
    preliminary = fuse_candidates(
        semantic + event_candidates(visual_events + chapter_events), config.semantic, source.duration_s
    )

    progress("[6/9] Reading on-screen text near likely boundaries")
    ocr_events: list[EvidenceEvent] = []
    if config.ocr.mode != "off":
        ocr_provider = ocr_provider or RapidOcrProvider(config.ocr)
        timestamps = [min(source.duration_s - 0.05, item.timestamp_s + 0.35) for item in preliminary]
        try:
            ocr_events = ocr_provider.recognize_at(media_path, timestamps)
        except Exception as exc:
            if config.ocr.mode == "on":
                raise
            warnings.append(f"OCR unavailable; continuing without OCR: {type(exc).__name__}: {exc}")
    _write_evidence(run_dir, "ocr-events", ocr_events)
    all_candidates = semantic + event_candidates(visual_events + chapter_events + ocr_events)
    boundaries = fuse_candidates(all_candidates, config.semantic, source.duration_s)
    _write_evidence(run_dir, "boundary-candidates", all_candidates)
    _write_evidence(run_dir, "boundaries", boundaries)
    segments = build_segments(boundaries, units, ocr_events, source.duration_s, transcript.language)

    progress("[7/9] Selecting the first meaningful frame for each segment")
    for segment in segments:
        segment.representative_frame = select_representative_frame(
            media_path, segment, run_dir / "frames", config.frame_selection
        )

    progress("[8/9] Running optional vision-capability fallback")
    vision_events, vision_warnings = recognize_segment_frames(
        run_dir, segments, config.vision_recognition, vision_recognizer
    )
    warnings.extend(vision_warnings)
    _write_evidence(run_dir, "vision-recognition", vision_events)
    render_visual_descriptions(run_dir, vision_events)

    progress("[9/9] Summarizing, rendering, and validating deliverables")
    render_transcript(run_dir, transcript)
    render_segments(run_dir, segments)
    if config.summary.enabled:
        render_video_summary(run_dir, segments, config.summary)
    render_frame_annotations(run_dir, segments, config.frame_annotation)
    atomic_write_json(
        run_dir / "segments.raw.json", {"schema_version": "1.0", "segments": jsonable(segments)}
    )
    if (run_dir / "overrides.json").exists():
        from .review import render_reviewed

        render_reviewed(run_dir)
        if config.summary.enabled:
            reviewed = read_json(run_dir / "segments.json")["segments"]
            # Summary is transcript-grounded; automatic segment objects remain the stable source.
            if reviewed:
                render_video_summary(run_dir, segments, config.summary)
    render_report(run_dir, segments, warnings)
    atomic_write_json(
        run_dir / "run.json",
        {
            "schema_version": "1.0",
            "run_id": run_id,
            "status": "complete",
            "source_sha256": source.sha256,
            "config_sha256": config_hash,
            "created_at": created_at,
            "updated_at": _now(),
            "completed_stages": [
                "probe", "transcript", "gap_audit", "visual", "semantic", "ocr",
                "frames", "vision_recognition", "summary", "render",
            ],
            "warnings": warnings,
            "software_versions": {"vseg": "0.4.0", "asr": transcript.provider},
        },
    )
    if sha256_file(media_path) != source.sha256:
        raise RuntimeError("source media changed during processing")
    errors = validate_run(run_dir)
    if errors:
        atomic_write_json(run_dir / "validation.json", {"valid": False, "errors": errors})
        raise RuntimeError("output validation failed: " + "; ".join(errors))
    atomic_write_json(run_dir / "validation.json", {"valid": True, "errors": []})
    checkpoint.save(
        "render",
        "complete",
        _stage_hash(source.sha256, "render"),
        config_hash,
        "vseg-render-v2",
        {"path": "segments.json"},
    )
    # Post-analysis organization: copy video, rename based on content
    final_run_dir = post_analysis_organize(run_dir, config, segments, vision_events, title_override)
    return final_run_dir
