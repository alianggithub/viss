# Video Semantic Segmenter (ViSS)

ViSS converts a local video into semantic chapters, a complete timestamped transcript,
transcript-grounded summary/key points, and meaningful annotated frames. Version 0.4
adds source-adjacent default output, annotated-only user timestamp dumps, and optional
local vision-model capability routing.

See [`USER-GUIDE.md`](USER-GUIDE.md) for the complete workflow and
[`DESIGN-v0.4.md`](DESIGN-v0.4.md) for the feature decisions.

## Install

Python 3.11 or newer and `uv` are required.

```bash
uv sync --extra dev                 # timestamp frame dumping
uv sync --extra all --extra dev     # full ASR/OCR analysis
```

For reproducible full-quality analysis, install from the checked-in lockfile and verify
that both Faster-Whisper and RapidOCR are importable:

```bash
uv sync --frozen --extra all --extra dev
uv run python -c \
  "from faster_whisper import WhisperModel; from rapidocr import RapidOCR; print('ASR and OCR ready')"
```

ViSS uses RapidOCR, not Tesseract. Keep one Faster-Whisper model cache outside the
project and analysis outputs, then pass its snapshot directory explicitly:

```bash
uv run vseg analyze "/video/trip.mp4" \
  --model "/models/faster-whisper-small" \
  --language zh --vision off
```

Use `--language auto` only when the language is unknown. An explicit shared model path
avoids downloading or embedding a separate `models/` cache in every analysis directory.
After processing, run `uv run vseg validate /video/trip-viss-analysis` and inspect
`report.md` and `run.json`. For quality-sensitive work, reject and rerun any result that
warns that ASR or OCR was unavailable. ViSS 0.4 can otherwise warn and continue with
reduced evidence. See the full quality checklist in `USER-GUIDE.md`.

## Dump annotated frames at user timestamps

```bash
uv run vseg dump-frames "/video/trip.mp4" \
  --timestamp '01:15|Temple entrance' \
  --timestamp '07:42|Mountain view'
```

With no `--output`, results go beside the source video:

```text
/video/trip.mp4
/video/trip-timestamp-frames/
```

Only final annotated JPEGs are retained under `frames/`; no second raw-image set or
`annotated/` subfolder is created. Use `--raw-and-annotated` only when the older two-set
layout is needed.

A timestamp file is also supported:

```text
# timestamps.txt
00:01:15 | Temple entrance
07:42 | Mountain view
```

```bash
uv run vseg dump-frames "/video/trip.mp4" --timestamps-file timestamps.txt
```

ViSS searches one second around each request by default and records both requested and
actual selected frame times. Use `--window`, `--sample-fps`, or `--no-fine-tune` to tune
selection. `--output DIR` always overrides the source-adjacent default.

## Analyze a video and summarize it

```bash
uv run vseg analyze "/video/trip.mp4" \
  --model small --language auto --allow-network-models
```

The default analysis directory is `/video/trip-viss-analysis/`. Important outputs now
include:

- `summary.md` and `summary.json`: whole-video overview and transcript-grounded key points;
- `key-points.md`: detailed key points grouped by semantic segment;
- `transcript/`: complete JSON, Markdown, text, SRT, and WebVTT transcript;
- `chapters.md` and `segments.json`: semantic structure;
- `frames/` and frame indexes: representative frames; and
- `visual-descriptions.md` and `evidence/vision-recognition.json`: optional vision results.

## Optional Nemotron vision recognition

ViSS's ASR and heuristic semantic provider cannot inspect image content. In `auto` mode,
ViSS therefore routes representative frames to the configured local vision endpoint
when it is available. The default fallback model ID is:

```text
nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8
```

Start a compatible local server separately, for example:

```bash
vllm serve "nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8"
```

Then run:

```bash
uv run vseg analyze "/video/trip.mp4" --vision on \
  --vision-endpoint http://127.0.0.1:8000/v1 \
  --vision-model nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8 \
  --model small --allow-network-models
```

`auto` warns and continues when the server/model is unavailable; `on` makes vision
recognition required; `off` disables it. ViSS does not silently download or launch a
12B vision model because that could consume substantial GPU memory or conflict with an
existing model. The local vLLM/SGLang server owns model loading.

## Existing commands

```bash
uv run vseg resume /video/trip-viss-analysis
uv run vseg validate /video/trip-viss-analysis
uv run vseg render /video/trip-viss-analysis
uv run vseg annotate-frames /video/trip-viss-analysis
```

Source videos are opened read-only. All defaults are configurable in
`config.example.yaml`.
