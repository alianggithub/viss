# ViSS 0.3 Design — User-Defined Timestamp Frame Dumping

Version: 0.3.0  
Date: 2026-07-23  
Status: Implemented

## Goal

A user can name one or more whole-second positions in a local video and obtain a clear,
useful image near each position. The feature must remain useful when the requested
second lands on motion blur, a fade, a black frame, or an intermediate transition.
It must work without ASR, OCR, semantic segmentation, or network access.

This is additive to the automatic per-segment representative frames introduced before
v0.2. Existing commands and analysis outputs remain compatible.

## Command contract

```text
vseg dump-frames INPUT
  (--timestamp TIME[|LABEL])...
  [--timestamps-file PATH]
  [--output OUTPUT_DIR]
  [--config PATH]
  [--window SECONDS]
  [--sample-fps FPS]
  [--no-fine-tune]
```

At least one `--timestamp` or one non-comment entry in `--timestamps-file` is required.
Direct and file requests may be combined; direct requests are processed first and file
requests retain file order.

Accepted time forms are non-negative whole seconds (`75`), `MM:SS` (`02:10`), and
`HH:MM:SS` (`01:02:03`). A label follows `|`. Blank lines and lines beginning with `#`
are ignored in a UTF-8/UTF-8-BOM timestamp file. Invalid forms, missing files, and times
beyond video duration are reported before image output is created. File errors include
the path and line number.

## Fine-tuning algorithm

For each request ViSS MUST:

1. clamp a search interval to source boundaries, defaulting to requested time ±1 second;
2. decode only that interval and sample candidates at a default 8 fps;
3. compute visual quality from exposure, contrast, and edge sharpness;
4. compute proximity as `1 - absolute_offset / search_window`;
5. rank by `0.8 * quality + 0.2 * proximity` by default;
6. resolve ties deterministically by quality, closeness, then earlier presentation time;
7. flag a result for review when quality is below the configured threshold; and
8. record every candidate score so the selection is auditable.

The exact requested second is not guaranteed to win. The chosen presentation timestamp
MUST stay inside the configured search interval. At video start/end, only the valid side
is searched. `--no-fine-tune` MUST choose the nearest decoded frame and still record the
actual presentation timestamp.

Presentation timestamps are authoritative. Any frame number is informational because
variable-frame-rate video cannot be represented reliably by timestamp × average FPS.

## Output contract

```text
OUTPUT_DIR/
├── frames/                 # unmodified extracted JPEGs
├── annotated/              # timestamp/label overlay copies
├── index.json              # canonical manifest and candidate audit
├── index.csv               # compact interoperable table
└── index.md                # human-readable linked table
```

Filenames contain stable request order, requested timestamp, selected timestamp, and an
optional path-safe Unicode label. The manifest records source path/hash/duration, all
selection parameters, requested and actual timestamps, signed offset, image paths,
quality/proximity/combined scores, review state, input provenance, and all candidates.
The JSON contract is described by `schemas/user-frame-index.schema.json`.

Rerunning into the same output folder removes stale JPEGs in the two managed image
folders and deterministically recreates indexes. Files outside those folders are not
removed. The source video is read-only.

## Configuration

```yaml
user_frame_dump:
  fine_tune: true
  search_window_s: 1.0
  sample_fps: 8.0
  quality_weight: 0.8
  proximity_weight: 0.2
  min_quality: 0.45
```

Weights are normalized, so they need not sum to one. Both cannot be zero. The search
window may be zero only when fine-tuning is disabled in practice; sampling must be
positive. CLI `--window` and `--sample-fps` override YAML for one invocation.

## Safety, performance, and compatibility

- Source bytes MUST NOT change.
- Output paths are user-selected and no cloud upload is performed.
- Memory use is bounded by one narrow interval's candidate images at a time.
- Multiple requests are processed in stable order; duplicate requests are preserved.
- The feature does not alter `segments.json`, automatic representative frames, or
  completed v0.2 runs.
- A v0.2 configuration without `user_frame_dump` receives v0.3 defaults.

## Verification requirements

Tests cover all accepted time forms; malformed and out-of-duration requests; comments,
labels, BOM input, and line diagnostics; exact versus quality-tuned ranking; beginning,
middle, and end behavior; raw/annotated images; JSON/CSV/Markdown indexes; candidate
audit fields; backward-compatible analysis tests; lint; build; and installed-wheel CLI
smoke tests.
