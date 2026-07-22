# ViSS v0.2.0 complete delivery

This combined delivery contains both implementation and design documentation.

## `video-semantic-segmenter-v0.2.0/`

The complete portable application:

- source code and configuration;
- JSON schemas, including the frame-index schema;
- unit and integration tests;
- README and full execution report;
- built v0.2.0 wheel and source distribution; and
- application-level `file-list.md`.

It excludes the host-specific `.venv`, caches, source videos, ASR model weights, and
processed-video outputs.

## `video-semantic-segmenter-spec/`

The updated v0.2 design package:

- `SPEC.md`: normative architecture, command/output contracts, frame annotation and
  indexing requirements, data model, configuration, validation, compatibility, and
  performance rules.
- `TASKS.md`: junior-agent implementation backlog with the frame-annotation/indexing
  task, tests, dependencies, and acceptance criteria.

## Related smaller archive

`video-semantic-segmenter-v0.2.0-2026-07-19.zip` remains the application-only
archive. The complete archive is the one to copy when both code and design documents
are wanted.
