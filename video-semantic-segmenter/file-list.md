# ViSS 0.2 delivery contents

- `README.md`: short installation, command, and output guide.
- `IMPLEMENTATION-REPORT.md`: full execution, review, deployment, and frame-index guide.
- `config.example.yaml`: example configuration, including frame annotation controls.
- `src/vseg/`: ViSS application source code.
- `schemas/`: machine-readable output schemas, including `frame-index.schema.json`.
- `tests/`: unit and integration tests.
- `pyproject.toml` and `uv.lock`: package and reproducible dependency definitions.
- `dist/`: prebuilt ViSS 0.2 wheel and source distribution.

The delivery archive intentionally excludes `.venv`, test/lint caches, and Python
bytecode. Create a fresh environment on the destination system with `uv sync`.

ViSS 0.2 adds annotated representative frames, timestamp/scene filenames,
`frames/index.json`, `frames/index.csv`, and `frames/index.md`. Existing ViSS 0.1
output can be upgraded without rerunning video analysis:

```bash
uv run vseg annotate-frames "/path/to/existing-run"
```
