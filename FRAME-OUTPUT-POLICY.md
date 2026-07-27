# ViSS Annotated-Only Frame Output Policy

Effective: ViSS 0.4.0 corrected build, 2026-07-25

ViSS retains one JPEG for every selected frame in both workflows:

- automatic representative frames from `vseg analyze`; and
- user-requested timestamps from `vseg dump-frames`.

The retained JPEG is the annotated image. It contains the actual source presentation
timestamp and, when available, the semantic segment title or user label. There is no
second unannotated set and no `frames/annotated/` directory.

For an analysis run:

```text
<analysis>/frames/
├── segment-0001.jpg       # annotated canonical image
├── segment-0002.jpg       # annotated canonical image
├── index.json
├── index.csv
└── index.md
```

`frames/index.json` schema 2.0 declares `output_mode: annotated_only` and exposes one
`frame_path`. `segments.json` references the same annotated canonical JPEG. Validation
fails if an annotated-only run still contains JPEGs under `frames/annotated/`.

The stable `segment-NNNN.jpg` filename preserves compatibility and rerender/review
behavior. Scene titles and timestamps remain searchable in all three indexes and visible
inside each JPEG. Re-annotation overwrites the canonical image rather than creating a
copy.

The optional `--raw-and-annotated` compatibility switch applies only to the standalone
`dump-frames` command. Automatic `analyze` output is always annotated-only.
