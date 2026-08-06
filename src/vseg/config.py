from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _data_home() -> Path:
    """Get the data home directory from env or default to ~/data/viss."""
    return Path(os.environ.get("VSEG_DATA_HOME", "~/data/viss")).expanduser()


@dataclass(slots=True)
class RuntimeConfig:
    device: str = "auto"
    workers: int = 2


@dataclass(slots=True)
class TranscriptionConfig:
    provider: str = "faster_whisper"
    model: str = "small"
    language: str = "auto"
    word_timestamps: bool = True
    vad: bool = True
    suspicious_gap_s: float = 8.0
    cpu_threads: int = 8


@dataclass(slots=True)
class VisualConfig:
    analysis_width: int = 320
    sample_fps: float = 2.0
    cut_threshold: float = 0.42
    black_threshold: float = 0.06


@dataclass(slots=True)
class OcrConfig:
    mode: str = "auto"
    max_frames_per_minute: int = 30


@dataclass(slots=True)
class SemanticConfig:
    provider: str = "heuristic"
    chunk_duration_s: float = 600.0
    chunk_overlap_s: float = 30.0
    candidate_merge_s: float = 1.5
    lexical_change_threshold: float = 0.67
    pause_threshold_s: float = 1.2
    min_candidate_score: float = 0.52


@dataclass(slots=True)
class FrameSelectionConfig:
    search_window_s: float = 8.0
    sample_fps: float = 3.0
    min_quality: float = 0.45
    min_relevance: float = 0.0


@dataclass(slots=True)
class OutputConfig:
    root: str = ""
    organize_by_default: bool = True
    rename_after_analysis: bool = True


@dataclass(slots=True)
class FrameAnnotationConfig:
    enabled: bool = True
    overlay_timestamp: bool = True
    overlay_scene_title: bool = True
    scene_aware_filenames: bool = True
    font_path: str | None = None
    font_size_ratio: float = 0.042
    jpeg_quality: int = 92
    max_scene_filename_chars: int = 64


@dataclass(slots=True)
class UserFrameDumpConfig:
    """Defaults for selecting a clear frame near a user-supplied timestamp."""

    fine_tune: bool = True
    search_window_s: float = 1.0
    sample_fps: float = 8.0
    quality_weight: float = 0.8
    proximity_weight: float = 0.2
    min_quality: float = 0.45
    annotated_only: bool = True


@dataclass(slots=True)
class VisionRecognitionConfig:
    """Optional capability fallback to an already running local vision model server."""

    mode: str = "auto"
    provider: str = "openai_compatible"
    endpoint: str = "http://127.0.0.1:8000/v1"
    model: str = "nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8"
    api_key: str | None = None
    timeout_s: float = 30.0
    max_tokens: int = 256


@dataclass(slots=True)
class SummaryConfig:
    enabled: bool = True
    max_key_points: int = 12
    max_points_per_segment: int = 2
    max_overview_topics: int = 12
    include_timestamps: bool = True


@dataclass(slots=True)
class PrivacyConfig:
    allow_network_models: bool = False
    retain_temporary_audio: bool = False


@dataclass(slots=True)
class Config:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    visual: VisualConfig = field(default_factory=VisualConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    frame_selection: FrameSelectionConfig = field(default_factory=FrameSelectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    frame_annotation: FrameAnnotationConfig = field(default_factory=FrameAnnotationConfig)
    user_frame_dump: UserFrameDumpConfig = field(default_factory=UserFrameDumpConfig)
    vision_recognition: VisionRecognitionConfig = field(default_factory=VisionRecognitionConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


_SECTIONS: dict[str, type[Any]] = {
    "runtime": RuntimeConfig,
    "transcription": TranscriptionConfig,
    "visual": VisualConfig,
    "ocr": OcrConfig,
    "semantic": SemanticConfig,
    "frame_selection": FrameSelectionConfig,
    "output": OutputConfig,
    "frame_annotation": FrameAnnotationConfig,
    "user_frame_dump": UserFrameDumpConfig,
    "vision_recognition": VisionRecognitionConfig,
    "summary": SummaryConfig,
    "privacy": PrivacyConfig,
}


def _strict_dataclass(cls: type[Any], values: dict[str, Any], section: str) -> Any:
    allowed = set(cls.__dataclass_fields__)
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"unknown configuration keys in {section}: {sorted(unknown)}")
    return cls(**values)


def load_config(path: Path | None) -> Config:
    if path is None:
        config = Config()
        config.output.root = str(_data_home() / "output")
        validate_config(config)
        return config
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    unknown = set(raw) - set(_SECTIONS)
    if unknown:
        raise ValueError(f"unknown configuration sections: {sorted(unknown)}")
    sections: dict[str, Any] = {}
    for name, cls in _SECTIONS.items():
        values = raw.get(name, {})
        if not isinstance(values, dict):
            raise ValueError(f"configuration section {name} must be a mapping")
        sections[name] = _strict_dataclass(cls, values, name)
    config = Config(**sections)
    # Set default output.root from data home if not provided
    if not config.output.root:
        config.output.root = str(_data_home() / "output")
    # Ensure output.root is always an expanded absolute path
    config.output.root = str(Path(config.output.root).expanduser())
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    if config.runtime.workers < 1:
        raise ValueError("runtime.workers must be >= 1")
    if config.transcription.suspicious_gap_s <= 0:
        raise ValueError("transcription.suspicious_gap_s must be > 0")
    if config.visual.sample_fps <= 0 or config.frame_selection.sample_fps <= 0:
        raise ValueError("sample_fps values must be > 0")
    if config.ocr.mode not in {"auto", "on", "off"}:
        raise ValueError("ocr.mode must be auto, on, or off")
    if config.runtime.device not in {"auto", "cpu", "cuda"}:
        raise ValueError("runtime.device must be auto, cpu, or cuda")
    annotation = config.frame_annotation
    if not 0.01 <= annotation.font_size_ratio <= 0.2:
        raise ValueError("frame_annotation.font_size_ratio must be between 0.01 and 0.2")
    if not 1 <= annotation.jpeg_quality <= 100:
        raise ValueError("frame_annotation.jpeg_quality must be between 1 and 100")
    if not 12 <= annotation.max_scene_filename_chars <= 160:
        raise ValueError("frame_annotation.max_scene_filename_chars must be between 12 and 160")
    dump = config.user_frame_dump
    if dump.fine_tune and dump.search_window_s <= 0:
        raise ValueError("user_frame_dump.search_window_s must be > 0 when fine_tune is enabled")
    if dump.sample_fps <= 0:
        raise ValueError("user_frame_dump.sample_fps must be > 0")
    if not 0 <= dump.min_quality <= 1:
        raise ValueError("user_frame_dump.min_quality must be between 0 and 1")
    if dump.quality_weight < 0 or dump.proximity_weight < 0:
        raise ValueError("user_frame_dump weights must be >= 0")
    if dump.quality_weight + dump.proximity_weight <= 0:
        raise ValueError("user_frame_dump weights must have a positive sum")
    vision = config.vision_recognition
    if vision.mode not in {"auto", "on", "off"}:
        raise ValueError("vision_recognition.mode must be auto, on, or off")
    if vision.provider != "openai_compatible":
        raise ValueError("vision_recognition.provider must be openai_compatible")
    if not vision.endpoint.startswith(("http://", "https://")):
        raise ValueError("vision_recognition.endpoint must be an HTTP(S) URL")
    if vision.timeout_s <= 0 or vision.max_tokens < 1:
        raise ValueError("vision_recognition timeout/max_tokens must be positive")
    summary = config.summary
    if min(summary.max_key_points, summary.max_points_per_segment, summary.max_overview_topics) < 1:
        raise ValueError("summary limits must be >= 1")
    output = config.output
    root = Path(output.root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError(f"output.root is not a directory: {output.root}")
