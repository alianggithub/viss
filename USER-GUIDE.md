# ViSS 0.4 User Guide

This guide covers Video Semantic Segmenter (ViSS), including semantic analysis,
whole-video transcript summaries, user-defined timestamp frames, source-adjacent output,
and optional Nemotron visual recognition.

## 1. Install

Timestamp frame dumping needs Python 3.11+, `uv`, and a readable video:

```bash
cd video-semantic-segmenter
uv sync --extra dev
uv run vseg --help
```

Full analysis needs ASR/OCR dependencies and a faster-whisper model:

```bash
uv sync --extra all --extra dev
```

### Reproducible full-quality installation

For semantic-boundary work, use the checked-in dependency lockfile and verify both
analysis engines before processing videos:

```bash
uv sync --frozen --extra all --extra dev
uv run python -c \
  "from faster_whisper import WhisperModel; from rapidocr import RapidOCR; print('ASR and OCR ready')"
```

ViSS uses RapidOCR, not Tesseract. Installing only the base or `dev` dependencies is
enough for `dump-frames`, but it is not a full semantic-analysis installation.

Keep one shared Faster-Whisper model cache outside the ViSS source tree and output
directories. For example:

```text
/models/faster-whisper-small/
```

Point every run at the same local snapshot:

```bash
uv run vseg analyze "/media/input.mp4" \
  --model "/models/faster-whisper-small" \
  --language zh \
  --vision off
```

Use the correct explicit language, such as `zh`, when it is known; use
`--language auto` when it is not. A shared local model path improves reproducibility,
works offline, and prevents each analysis directory from receiving a large `models/`
download cache. If the model must be downloaded initially, use
`--model small --allow-network-models` once, preserve the resulting model cache in a
shared location, and use its local snapshot path for subsequent runs.

After every quality-sensitive run:

```bash
uv run vseg validate "/media/input-viss-analysis"
```

Inspect both `report.md` and `run.json`. Treat warnings such as `OCR unavailable`,
`ASR unavailable`, or suspicious unrecovered transcription gaps as a failed
quality-sensitive run even if ViSS completed. ViSS 0.4 does not yet have a strict
quality flag and can intentionally continue without optional OCR.

Nemotron is not required to reproduce semantic boundary quality. In ViSS 0.4 it
describes and rates representative frames after segmentation; it does not select the
semantic boundary timestamps. Use `--vision on` when those visual descriptions are
needed, not as a replacement for ASR/OCR readiness.

Do not copy `.venv` between computers. Recreate it with `uv sync`. No ASR, OCR, GPU,
network access, or prior ViSS analysis is required for `dump-frames`.

## 2. Where output goes

When `--output` is omitted, ViSS creates a sibling directory beside the source video.
For `/media/trip.mp4`:

```text
/media/trip-timestamp-frames/   # dump-frames
/media/trip-viss-analysis/      # analyze
```

This is based on the resolved source-video path, not the shell's current directory.
Override it at any time:

```bash
uv run vseg dump-frames /media/trip.mp4 --timestamp 75 --output /work/frames
uv run vseg analyze /media/trip.mp4 --output /work/analysis --model small
```

ViSS never writes JPEGs loose beside the video; the sibling folder keeps indexes and
images together. The source video is read-only and its SHA-256 is recorded.

## 3. Dump frames at user timestamps

Accepted whole-second forms are:

| Form | Example | Meaning |
|---|---|---|
| Seconds | `75` | 1 minute 15 seconds |
| Minutes/seconds | `01:15` | 1 minute 15 seconds |
| Hours/minutes/seconds | `00:01:15` | 1 minute 15 seconds |

Negative, decimal, malformed, and beyond-duration timestamps are errors. Add an optional
label after `|`; quote a labeled shell argument because `|` is a shell operator.

```bash
uv run vseg dump-frames "/media/trip.mp4" \
  --timestamp '00:00|Opening' \
  --timestamp '01:15|Temple entrance' \
  --timestamp '07:42|Mountain view'
```

### Timestamp file

Create a UTF-8 file. Blank lines and `#` comments are ignored:

```text
# timestamps.txt
00:00 | Opening
01:15 | Temple entrance
07:42 | Mountain view
600
```

```bash
uv run vseg dump-frames /media/trip.mp4 --timestamps-file timestamps.txt
```

Direct arguments and file entries may be combined. Direct entries come first; file
order is retained. Duplicate timestamps are preserved. File errors show path and line.
All requests are duration-validated before frame output begins.

### Fine-tuned selection

A requested second can land on motion blur, a fade, or a dark transition. The default
search samples one second on either side at 8 fps and ranks candidates with 80% visual
quality (exposure, contrast, sharpness) and 20% temporal proximity.

```bash
# Search farther
uv run vseg dump-frames input.mp4 --timestamp 75 --window 2

# Sample fast action more densely
uv run vseg dump-frames input.mp4 --timestamp 75 --window 1.5 --sample-fps 15

# Select the nearest decoded frame without quality tuning
uv run vseg dump-frames input.mp4 --timestamp 75 --no-fine-tune
```

The image and index record actual selected time. `offset_s` is selected minus requested
time. `needs_review` marks a result below the configured quality threshold.

### Annotated-only output

The default layout contains only the final annotated images:

```text
trip-timestamp-frames/
├── frames/
│   └── 0001__requested-00-01-15-000__actual-00-01-15-375__Temple-entrance.jpg
├── index.json
├── index.csv
└── index.md
```

There is no retained raw-image set and no `annotated/` subfolder. ViSS briefly uses one
local temporary JPEG to render the overlay and deletes it immediately. JSON/CSV/Markdown
all reference one canonical `frame_path`.

For compatibility with older automation:

```bash
uv run vseg dump-frames input.mp4 --timestamp 75 --raw-and-annotated
```

That opt-out restores `frames/` raw images and `annotated/` copies.

## 4. Full semantic analysis and key-point summary

Run analysis with a local ASR model directory:

```bash
uv run vseg analyze /media/trip.mp4 \
  --model /models/faster-whisper-small --language auto
```

Or explicitly allow the named ASR model to download on first use:

```bash
uv run vseg analyze /media/trip.mp4 \
  --model small --language auto --allow-network-models
```

In addition to the complete transcript, ViSS produces:

- `summary.md`: quick whole-video overview, key points, and chapter list;
- `summary.json`: the same data with segment IDs, timestamps, confidence, and evidence;
- `key-points.md`: more detailed key points grouped by semantic segment;
- `chapters.md`: compact chapter timeline; and
- `transcript/`: complete JSON, Markdown, text, SRT, and WebVTT forms.

The summary is extractive and transcript-grounded: it selects distinct key points from
all semantic segments in round-robin order so early long segments do not crowd out later
topics. Every JSON point retains transcript evidence references. Defaults are:

```yaml
summary:
  enabled: true
  max_key_points: 12
  max_points_per_segment: 2
  max_overview_topics: 12
  include_timestamps: true
```

This summarization works offline without an LLM. It favors traceability over creative
abstraction. Segment-level `key-points.md` remains available when more detail is needed.

## 5. Optional vision recognition and Nemotron fallback

### Why a fallback exists

The faster-whisper model understands audio, not images. ViSS's default semantic provider
is also transcript heuristics, not a vision-language model. Therefore neither is treated
as vision-capable. When `vision_recognition.mode` is `auto`, ViSS checks the configured
local OpenAI-compatible endpoint and routes representative frames to its specialized
vision model when present.

The default model ID is:

```text
nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8
```

It supports image/text input and OpenAI-compatible serving through vLLM. If your server
advertises a different alias, put that exact ID in `model` or `--vision-model`.

### Start the model server

Model loading belongs to the serving layer. One example is:

```bash
vllm serve "nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8" \
  --host 127.0.0.1 --port 8000
```

Then analyze:

```bash
uv run vseg analyze /media/trip.mp4 \
  --model small --allow-network-models \
  --vision on \
  --vision-endpoint http://127.0.0.1:8000/v1 \
  --vision-model nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8
```

Modes:

- `auto` (default): use the local vision model if advertised; otherwise warn and finish.
- `on`: require it; endpoint/model errors stop the run.
- `off`: skip general vision recognition.

Outputs are `visual-descriptions.md` and `evidence/vision-recognition.json`. Each event
records model identity, segment/frame, factual description, raw response, and optional
relevance score. Relevance is also copied into the representative-frame decision.

### Why ViSS does not silently launch/download it

Nemotron Nano VL is a 12.6B-parameter model. Automatically downloading or starting it
could unexpectedly consume disk, GPU memory, and startup time, or evict a model already
serving other work. ViSS therefore performs automatic capability routing, but requires
the operator to start/load the server. This division is deterministic and works with
vLLM or SGLang OpenAI-compatible deployments.

Configuration:

```yaml
vision_recognition:
  mode: auto
  provider: openai_compatible
  endpoint: http://127.0.0.1:8000/v1
  model: nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8
  api_key: null
  timeout_s: 30.0
  max_tokens: 256
```

The endpoint should normally be loopback for local privacy. `api_key` is written into
the effective configuration; prefer a protected config file and do not publish it.

## 6. Configuration and outputs

Copy `config.example.yaml`, edit it, then pass `--config`:

```bash
uv run vseg analyze input.mp4 --config my-viss.yaml --model small
uv run vseg dump-frames input.mp4 --config my-viss.yaml --timestamps-file timestamps.txt
```

Main analysis outputs:

```text
<video>-viss-analysis/
├── source.json, run.json, config.effective.yaml
├── summary.md, summary.json
├── chapters.md, key-points.md, segments.json
├── visual-descriptions.md
├── transcript/
├── frames/
├── evidence/
├── checkpoints/
└── validation.json, report.md
```

## 7. Resume, validate, review, and rerender

```bash
uv run vseg resume /media/trip-viss-analysis
uv run vseg validate /media/trip-viss-analysis
uv run vseg render /media/trip-viss-analysis
uv run vseg annotate-frames /media/trip-viss-analysis
uv run vseg review /media/trip-viss-analysis segment-0002 \
  --title 'Corrected title' --reviewer alice --verified
```

## 8. Troubleshooting

- `invalid timestamp`: use whole seconds, `MM:SS`, or `HH:MM:SS`.
- `beyond video duration`: correct/remove the entry; no index is written.
- `no decodable frame`: retry with a wider window and check for source corruption.
- `needs_review: true`: inspect the best candidate or widen the window.
- `vision model unavailable`: start the local server, match its advertised model ID,
  switch to `--vision off`, or retain default `auto` to continue without it.
- Vision timeout: confirm GPU readiness and increase `vision_recognition.timeout_s`.
- Non-empty analysis output: use `resume`, a new `--output`, or `--force-new-run`.
- `OCR unavailable`: install with `uv sync --frozen --extra all --extra dev`, rerun the
  ASR/OCR import check in section 1, and rerun analysis for quality-sensitive work.
- Unexpected `models/` inside an analysis output: the run used
  `--allow-network-models`; move one complete cache to a shared location and pass its
  snapshot directory with `--model` on future runs.

Keep `index.json`, `run.json`, and evidence files when reporting issues; they make frame
and model decisions reproducible.

---

## 9. FAQ & Session Notes (2026-07-27)

### Q: What's the difference between RapidOCR and Nemotron?

| Aspect | RapidOCR | Nemotron (vision) |
|---|---|---|
| Role | **OCR** — reads on-screen text | **Vision recognition** — describes frame content in natural language |
| Pipeline step | Step 6/9: "Reading on-screen text near likely boundaries" | Step 8/9: "Running optional vision-capability fallback" |
| Output | `evidence/ocr-events.json` (structured text detections) | `visual-descriptions.md`, `evidence/vision-recognition.json` |
| Model | PP-OCRv6 (onnxruntime, local) | NVIDIA Nemotron-Nano-12B-v2-VL (VLM, needs NIM/vLLM endpoint) |
| Purpose | Supporting evidence for boundary decisions | Human-readable visual descriptions of each segment's representative frame |

**Key insight**: Nemotron is **not an OCR model**. It does not extract text. It generates
semantic descriptions like "A 3D molecular model of water molecules..." or "A series of
purple podiums with national flags..." — useful for understanding visual context, not
for reading text.

### Q: If I don't use `--vision on`, what do I lose?

Only two files:
- `visual-descriptions.md` — natural-language descriptions per segment
- `evidence/vision-recognition.json` — structured VLM responses with confidence

Everything else is identical:
- Segment titles (from transcript + visual cuts + OCR)
- Scene-aware frame filenames (`0001__00-00-00-000__家比较.jpg`)
- Timestamp + scene title overlays on frames
- `key-points.md`, `chapters.md`, `summary.md`, transcript
- OCR evidence (`ocr-events.json`)
- Visual transition evidence (`visual-events.json`)

### Q: How does frame selection work?

1. **Boundaries decided first** (steps 1-5): transcript heuristics + visual cuts + OCR
2. **Then representative frame picked** (step 7): searches first 8s of each segment at 3 fps,
   picks first frame passing quality ≥ 0.45
3. **Then annotated** (step 9): timestamp + scene title overlaid, saved with scene-aware name

The filename pattern: `{index:04d}__{timestamp}__{scene_slug}.jpg`

### Q: What does `--vision on` actually add to the output files?

```text
With --vision on:
  visual-descriptions.md          ← NEW: "A 3D molecular model of water molecules..."
  evidence/vision-recognition.json ← NEW: structured VLM responses

Without --vision on:
  (these two files don't exist)
```

Everything else is the same.

### Q: How do I run with Nemotron via NVIDIA NIM (cloud endpoint)?

```bash
# Config file approach (recommended for API keys)
cat > my-nim-config.yaml <<'EOF'
vision_recognition:
  mode: on
  provider: openai_compatible
  endpoint: https://integrate.api.nvidia.com/v1
  model: nvidia/nemotron-nano-12b-v2-vl
  api_key: nvapi-xxxxxxxxxxxxxxxxx
  timeout_s: 30.0
  max_tokens: 256
EOF

uv run vseg analyze video.mp4 --config my-nim-config.yaml --model small --allow-network-models
```

### Q: Frame output layout — why no `annotated/` subfolder?

ViSS 0.4 writes annotated frames **directly to `frames/`** with scene-aware names:
```
frames/
  0001__00-00-00-000__Opening.jpg
  0002__00-01-15-200__Temple-entrance.jpg
  index.json, index.csv, index.md
```
No `annotated/` subfolder, no duplicate raw frames. This matches the pattern in
`~/doc/travel/planning/candidate/最美的三十个神仙秘境-semantic-segmented/frames/annotated/`
but without the extra folder level. Use `--raw-and-annotated` on `dump-frames` if you
need the legacy layout.

### Q: What are the three configurations I can compare in my test runs?

| Config | Directory | ASR | OCR | Vision |
|---|---|---|---|---|
| v0.2.0 | `WeChatAppEx_*/` | faster-whisper | RapidOCR | ❌ |
| v0.4.0 | `WeChatAppEx_*-viss-analysis/` | faster-whisper | RapidOCR | ❌ |
| v0.4.0 + Nemotron | `WeChatAppEx_*-viss-analysis-nemotron/` | faster-whisper | RapidOCR | ✅ Nemotron-Nano-12B-v2-VL |

All three share: same source videos, same frame annotation style, same index format.
Nemotron adds only `visual-descriptions.md` and `vision-recognition.json`.

---

*Session conducted 2026-07-27 with Hermes Agent. Full processing log in
`SESSION-NOTES-2026-07-27.md`.*