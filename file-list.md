# ViSS 0.4 Working-Tree File Guide

- `README.md` — quick commands for analysis, summaries, timestamp frames, and vision.
- `USER-GUIDE.md` — complete operator guide, reproducible full-quality installation,
  validation checklist, and troubleshooting.
- `DESIGN-v0.4.md` — normative contract for the four new features.
- `DESIGN-v0.3.md` — original user-timestamp fine-tuning design.
- `RELEASE-NOTES-v0.4.0.md` — v0.4 changes and compatibility.
- `VERIFICATION.md` — current test/lint/lock evidence and deferred packaging status.
- `IMPLEMENTATION-REPORT.md` — original v0.2 semantic-pipeline execution guide.
- `config.example.yaml` — all defaults, including timestamp, vision, and summary sections.
- `src/vseg/user_frames.py` — timestamp parsing, selection, and annotated-only output.
- `src/vseg/vision.py` — local OpenAI-compatible vision capability adapter.
- `src/vseg/summarize.py` — transcript-grounded whole-video summary.
- `src/vseg/pipeline.py` and `cli.py` — orchestration and command-line integration.
- `schemas/` — machine-readable output contracts.
- `tests/` — original regressions and v0.3/v0.4 feature tests.

No source videos, processed samples, model weights, virtual environment, caches, or
previous ZIP files are included in the release archive.
