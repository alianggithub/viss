from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


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
        return Config()
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
