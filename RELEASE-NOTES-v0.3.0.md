# ViSS 0.3.0 Release Notes

Released: 2026-07-23

## Added

- `vseg dump-frames` for extracting frames at user-defined timestamps without ASR.
- Repeatable `--timestamp` and UTF-8 `--timestamps-file` input.
- Whole-second, `MM:SS`, and `HH:MM:SS` parsing with optional labels.
- Configurable nearby-frame fine-tuning using visual quality and timestamp proximity.
- Raw and visibly annotated JPEGs with requested/actual times in filenames.
- Auditable JSON plus spreadsheet-friendly CSV and linked Markdown indexes.
- Input line diagnostics, video-duration validation, source hashing, review flags, and
  boundary-safe searches.
- `DESIGN-v0.3.md`, `USER-GUIDE.md`, JSON schema, configuration examples, and tests.

## Compatibility

This is an additive minor release over ViSS 0.2. Existing `analyze`, `resume`, `validate`,
`render`, `annotate-frames`, `review`, and `evaluate` behavior is retained. Existing
configuration files remain valid because the new section has defaults. Timestamp frame
dumping does not alter semantic-analysis runs or source videos.

## Verification

The release test, lint, build, installed-wheel CLI, archive-integrity, and source-tree
checks are recorded in `VERIFICATION.md`.
