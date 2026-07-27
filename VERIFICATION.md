# ViSS 0.4 Verification

Date: 2026-07-25

- Automated tests: **33 passed**.
- Static lint: **passed**.
- Dependency lock: consistent at version 0.4.0.
- Full-quality deployment procedure documents frozen dependency installation,
  Faster-Whisper/RapidOCR verification, and a shared external ASR model cache.
- Automatic analysis and user timestamp dumps retain one annotated JPEG per selection.
- Frame index schema 2.0 uses `output_mode: annotated_only` and one `frame_path`.
- Validator rejects duplicate JPEGs under `frames/annotated/` in annotated-only runs.
- Original ViSS semantic-analysis regressions: passed.
- Transcript-grounded summary and dynamic vision-adapter tests: passed.
- Two supplied videos: processed and validated with local faster-whisper-small and
  RapidOCR; their source hashes remained unchanged.
- Both supplied-video outputs were retrofitted: 2 segments/2 JPEGs and 27 segments/27
  JPEGs, with no second frame sets; both corrected runs validated again.

Live Nemotron inference was not exercised because no model server was running. Source
archive excludes model weights, videos, processing outputs, caches, and `.venv`.
