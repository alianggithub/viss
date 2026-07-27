# ViSS 0.4.0 Source Archive Manifest

This archive contains the complete reusable application source, tests, schemas,
configuration example, dependency lock, design documents, release notes, user guide,
and verification record.

Excluded intentionally:

- `.venv/` and Python bytecode/caches;
- `dist/` and previously built packages;
- source videos and processed video outputs;
- ASR/OCR/Nemotron model weights and caches; and
- credentials or environment-specific runtime state.

After extraction:

```bash
uv sync --frozen --extra all --extra dev
uv run python -c \
  "from faster_whisper import WhisperModel; from rapidocr import RapidOCR; print('ASR and OCR ready')"
uv run vseg --help
```

See `USER-GUIDE.md` for full analysis, timestamp-frame, summary, and optional local
vision-model commands and the reproducible full-quality installation checklist.
Version: 0.4.0. Automated verification: 33 tests passed, lint passed, and dependency
lock checked before packaging.
