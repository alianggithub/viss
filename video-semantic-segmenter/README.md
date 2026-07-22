# Video Semantic Segmenter

`vseg` turns a local video into semantic chapters, key points, a complete timestamped
transcript, and one early meaningful frame per segment. It uses the full transcript as
the primary signal and treats scene changes and OCR as supporting evidence.

For a complete preparation checklist, copyable execution commands, review workflow,
troubleshooting, and the implementation results, see
[`IMPLEMENTATION-REPORT.md`](IMPLEMENTATION-REPORT.md).

## Install

Python 3.11 or newer is required.

```bash
uv sync --extra all --extra dev
```

Models are local-only by default. Either provide a local faster-whisper model directory
with `--model`, or explicitly permit downloading a named model on the first run.
ASR means Automatic Speech Recognition: this model converts the video's speech into the
timestamped transcript used for semantic segmentation. The tested and recommended
starting model is `small`. See `IMPLEMENTATION-REPORT.md` for model-size guidance.

```bash
uv run vseg analyze input.mp4 --output output/run-1 \
  --model /path/to/faster-whisper-model --language auto

uv run vseg analyze input.mp4 --output output/run-1 \
  --model small --allow-network-models
```

Resume or validate a run:

```bash
uv run vseg resume output/run-1
uv run vseg validate output/run-1
uv run vseg render output/run-1
uv run vseg review output/run-1 segment-0002 --title "Corrected title" \
  --frame-timestamp 42.5 --reviewer alice --verified
uv run vseg evaluate output/run-1 reference-annotations.json
```

See [`../video-semantic-segmenter-spec/SPEC.md`](../video-semantic-segmenter-spec/SPEC.md)
for the implementation contract and
[`../video-semantic-segmenter-spec/TASKS.md`](../video-semantic-segmenter-spec/TASKS.md)
for the engineering breakdown.

## Outputs

- `segments.json`: canonical semantic segments and evidence references
- `chapters.md`: compact chapter list
- `key-points.md`: segment-level key points
- `transcript/`: JSON, text, SRT, and WebVTT transcript forms
- `frames/`: representative frames
- `evidence/`: visual, OCR, gap-audit, candidate, and fused-boundary records
- `validation.json` and `report.md`: quality and review summary
- `segments.raw.json` and `overrides.json`: immutable automatic result plus review audit

The source MP4 is read-only. Output paths are contained within the selected run
directory, and resumable metadata is keyed by source and configuration hashes.

## Operational notes

- Named ASR models are never downloaded unless `--allow-network-models` is supplied.
- `ocr: auto` continues without OCR when the provider is unavailable; `ocr: on` fails.
- Long VAD gaps with visual activity are retranscribed without VAD.
- Codec or truncated-file errors are reported during probing and do not modify the source.
- Use a smaller ASR model or lower visual sampling rates when CPU or memory is constrained.
- Human review changes rendered outputs through `overrides.json`; transcript and evidence files
  remain untouched, and overrides are reapplied after resume.
