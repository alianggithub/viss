# ViSS 0.4.0 Release Notes

Date: 2026-07-25  
Packaging: complete field source package

## Added or changed

- Default `analyze` and `dump-frames` output folders are beside the source video.
- Timestamp dumps retain only annotated frames and expose one canonical `frame_path`.
- `--raw-and-annotated` preserves the v0.3 two-set layout when needed.
- Optional OpenAI-compatible vision routing defaults to Nemotron Nano 12B v2 VL FP8.
- Vision `auto`, `on`, and `off` modes, model/endpoint CLI overrides, evidence JSON,
  human-readable descriptions, and representative-frame relevance scores.
- Whole-video `summary.md` and `summary.json`, grounded in semantic-segment transcript
  evidence and balanced across topics.
- Output validation for summary and vision artifacts.
- Updated configuration, schema, design, README, user guide, and tests.
- Added reproducible full-quality installation instructions: frozen dependency sync,
  ASR/OCR import verification, shared model cache, explicit language selection,
  post-run validation, and degraded-run warning criteria.

## Compatibility

Existing explicit `--output` behavior is unchanged. Existing v0.3 timestamp input and
fine-tuning remain supported. Automatic semantic-run representative-frame paths retain
the v0.2 contract. Old timestamp-dump consumers can request `--raw-and-annotated`.

ViSS performs automatic vision capability routing but intentionally leaves model
download and server startup to the local serving environment.
