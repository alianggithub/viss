# Video Semantic Segmenter — Implementation Report and Execution Guide

## 1. Status

The reusable version-one implementation is complete. It accepts a local video and
produces:

- semantic chapter timestamps;
- segment titles and key points;
- a complete timestamped transcript in JSON, Markdown, text, SRT, and WebVTT;
- one early meaningful JPEG frame for every segment;
- OCR, visual-transition, transcript-gap, and boundary evidence;
- resumable checkpoints, validation results, and an audit log; and
- non-destructive human review overrides.

The implementation does not contain names, phrases, timestamps, or paths learned from
the proof-of-concept video.

Verification completed on 2026-07-16:

- lint: passed;
- automated tests: 9 passed;
- Python wheel and source package: built successfully;
- supplied-video regression: 81 validated segments and 81 representative frames;
- source-integrity check: the MP4 SHA-256 remained unchanged; and
- output validation: passed.

The remaining product-level evaluation is to run the supplied evaluation command on
two or more additional human-annotated videos. This is measurement work, not missing
pipeline implementation.

## 2. Where the documentation is

- `README.md`: short installation and command reference.
- `IMPLEMENTATION-REPORT.md`: this complete operator guide and implementation report.
- `../video-semantic-segmenter-spec/SPEC.md`: normative design and data contracts.
- `../video-semantic-segmenter-spec/TASKS.md`: engineering task breakdown.
- `config.example.yaml`: all supported configuration sections and defaults.
- `schemas/`: machine-readable JSON schemas.

## 3. What to prepare for another video

Required:

1. A readable local video file. MP4 is the supported version-one input; formats
   readable by PyAV may also work.
2. A new or empty output directory, or an existing run directory when resuming.
3. Python 3.11 or newer and the `uv` executable.
4. A faster-whisper model:
   - allow the program to download a named model on the first run; or
   - supply the path to an existing local faster-whisper model snapshot.
5. Enough free space for the environment, model, transcript, evidence, and selected
   frames. The `small` ASR model is roughly 500 MB; allow at least 1–2 GB beyond the
   source video for a comfortable first run.

Helpful but optional:

- The spoken-language code, such as `zh`, `en`, or `ja`. Use `auto` when unknown.
- A configuration YAML copied from `config.example.yaml` when defaults need tuning.
- A CUDA-capable environment for acceleration. CPU operation is fully supported.
- Human reference annotations when objective precision/recall evaluation is desired.

You do **not** need to extract MP3 audio, dump video frames, or run OCR beforehand.
The pipeline decodes audio/video directly and retains only selected frames.

### What the ASR model is

ASR means **Automatic Speech Recognition**. The ASR model listens to the video's audio
and converts speech into text with timestamps. This project uses `faster-whisper`, an
optimized implementation of Whisper. The rest of the pipeline uses its transcript to
identify topics, generate key points, and locate likely segment boundaries.

The ASR model is a separate data package and is not included in the small project wheel
or source ZIP. The tested default is `small`, which is approximately 500 MB and offers
a practical CPU-speed/accuracy balance for multilingual material, including Chinese and
English.

Common choices are:

| Model | Relative speed | Relative accuracy | Suggested use |
| --- | --- | --- | --- |
| `tiny` or `base` | Fastest | Lower | Quick experiments or limited hardware |
| `small` | Moderate | Good | Recommended starting point; tested here |
| `medium` | Slower | Better | Difficult speech when more CPU/RAM is available |
| `large-v3` | Slowest/heaviest | Highest | Accuracy-focused GPU or powerful systems |

Use a named model plus `--allow-network-models` to download it, or copy an existing
faster-whisper model snapshot and supply its directory path to `--asr-model`. A valid
local snapshot normally contains `model.bin`, `config.json`, and `tokenizer.json`.

## 4. First-time installation

```bash
cd /nobackup/chrgu/test/video-semantic-segmenter
/auto/binos-tools/bin/uv sync --extra all --extra dev
```

Confirm the command is installed:

```bash
.venv/bin/vseg --help
```

The `uv run vseg` form shown below also works and automatically uses the project
environment.

## 5. Analyze another video

### Option A: let the first run download the ASR model

This is the simplest first-time command. It explicitly permits network model access.

```bash
cd /nobackup/chrgu/test/video-semantic-segmenter

/auto/binos-tools/bin/uv run vseg analyze \
  "/path/to/new-video.mp4" \
  --output "/path/to/new-video-analysis" \
  --asr-model small \
  --language auto \
  --ocr auto \
  --device cpu \
  --allow-network-models
```

Use `--language zh` for known Chinese speech. A known language generally avoids an
unnecessary detection error.

### Option B: completely offline using a local ASR model

Point `--asr-model` to a faster-whisper snapshot containing files such as `model.bin`,
`config.json`, and `tokenizer.json`:

```bash
/auto/binos-tools/bin/uv run vseg analyze \
  "/path/to/new-video.mp4" \
  --output "/path/to/new-video-analysis" \
  --asr-model "/path/to/faster-whisper-small-snapshot" \
  --language auto \
  --ocr auto \
  --device cpu
```

Network model access is disabled unless `--allow-network-models` is present.

### Use a configuration file

```bash
cp config.example.yaml my-video-config.yaml

/auto/binos-tools/bin/uv run vseg analyze \
  "/path/to/new-video.mp4" \
  --output "/path/to/new-video-analysis" \
  --config my-video-config.yaml \
  --asr-model "/path/to/local-model" \
  --language zh
```

Command-line values override the equivalent configuration-file values.

## 6. Resume, validate, and rerender

If a run is interrupted, resume it without creating a second run:

```bash
/auto/binos-tools/bin/uv run vseg resume "/path/to/new-video-analysis"
```

Validate all required files, time coverage, frame paths, and frame timestamps:

```bash
/auto/binos-tools/bin/uv run vseg validate "/path/to/new-video-analysis"
```

Rerender from the immutable automatic result plus any review overrides:

```bash
/auto/binos-tools/bin/uv run vseg render "/path/to/new-video-analysis"
```

To deliberately create another run when the chosen output directory is already in
use, add `--force-new-run`. A timestamped run subdirectory will be created.

## 7. Human review commands

Automatic transcript and evidence files are never edited by review operations.
Corrections are appended to `overrides.json` and reapplied whenever the run is
rendered or resumed.

Correct and verify a title:

```bash
/auto/binos-tools/bin/uv run vseg review \
  "/path/to/new-video-analysis" segment-0002 \
  --title "Corrected attraction name" \
  --reviewer chrgu \
  --verified
```

Adjust a boundary. The neighboring segment is adjusted to preserve continuous
coverage:

```bash
/auto/binos-tools/bin/uv run vseg review \
  "/path/to/new-video-analysis" segment-0002 \
  --start 42.5 \
  --reviewer chrgu \
  --verified
```

Choose a different representative frame:

```bash
/auto/binos-tools/bin/uv run vseg review \
  "/path/to/new-video-analysis" segment-0002 \
  --frame-timestamp 45.2 \
  --reviewer chrgu \
  --verified
```

The requested boundary or frame timestamp must remain inside valid source/segment
time ranges.

## 8. Outputs to inspect first

After a successful run, start with:

- `chapters.md`: timestamp and title for each semantic segment;
- `key-points.md`: summarized content for each segment;
- `transcript/transcript.md`: readable complete transcript;
- `frames/`: representative frames;
- `report.md`: warning and review summary; and
- `segments.json`: canonical machine-readable result.

Additional audit artifacts include:

```text
config.effective.yaml
run.json
source.json
segments.raw.json
overrides.json                 # appears after human review
validation.json
evidence/audio-events.json
evidence/visual-events.json
evidence/ocr-events.json
evidence/boundary-candidates.json
evidence/boundaries.json
checkpoints/
logs/run.jsonl
```

## 9. Evaluate against human annotations

Prepare a JSON file like this:

```json
{
  "segments": [
    {
      "title": "Expected topic",
      "start_s": 42.0,
      "boundary_tolerance_s": 10.0,
      "acceptable_frame_ranges": [[42.5, 48.0]]
    }
  ]
}
```

Then run:

```bash
/auto/binos-tools/bin/uv run vseg evaluate \
  "/path/to/new-video-analysis" \
  "/path/to/reference-annotations.json"
```

Detailed results are written to `evaluation.json`.

## 10. Practical limitations and troubleshooting

- Proper names depend on ASR and OCR quality. Unclear names should be reviewed.
- Music-only or lightly narrated videos provide less semantic evidence and may need
  manual boundary correction.
- Use `--ocr off` if OCR is unnecessary or its runtime is undesirable.
- `--ocr on` treats an unavailable OCR provider as an error; `--ocr auto` continues
  without it.
- If a named ASR model is not cached, either add `--allow-network-models` or provide a
  local snapshot path.
- If processing stops, use `vseg resume`; do not start another analysis in the same
  directory without `--resume`.
- A corrupt or truncated input is rejected during probing. The source is never edited.
- For limited CPU or memory, choose a smaller ASR model and lower visual/frame sample
  rates in the YAML configuration.

## 11. Supplied-video regression result

The final reusable pipeline output is located at:

```text
/nobackup/chrgu/test/神奇美景在中国-宋春玲/generic-vseg-output
```

It contains 81 validated segments, 81 representative frames, the complete transcript,
OCR/visual/audio evidence, checkpoints, logs, and validation metadata.

## 12. Deploy to another system

Do not copy the existing `.venv` as the target environment. It was created for this
host and contains an absolute command shebang and a Python symlink to this system.
Recreate `.venv` on the destination.

### Create a portable source archive

Run from the parent directory:

```bash
cd /nobackup/chrgu/test

zip -r video-semantic-segmenter-0.1.0-source.zip \
  video-semantic-segmenter \
  -x 'video-semantic-segmenter/.venv/*' \
     'video-semantic-segmenter/.pytest_cache/*' \
     'video-semantic-segmenter/.ruff_cache/*' \
     'video-semantic-segmenter/src/vseg/__pycache__/*' \
     'video-semantic-segmenter/tests/*/__pycache__/*'
```

Keep these files in the archive:

- `src/`, `schemas/`, and optionally `tests/`;
- `pyproject.toml` and `uv.lock`;
- `README.md`, `IMPLEMENTATION-REPORT.md`, and `config.example.yaml`; and
- `dist/`, which contains the prebuilt pure-Python project wheel and source archive.

### Install on the destination

The recommended destination system has Linux, Python 3.11 or newer, `uv`, sufficient
disk space, and network access for the initial dependency/model installation.

```bash
unzip video-semantic-segmenter-0.1.0-source.zip
cd video-semantic-segmenter

uv sync --frozen --extra all
.venv/bin/vseg --help
```

Then use `.venv/bin/vseg analyze ...`, or replace it with `uv run vseg analyze ...`.
For optional deployment tests, install the development extra with
`uv sync --frozen --extra all --extra dev`, then run `.venv/bin/pytest`.

### ASR model deployment

The source archive does not contain the approximately 500 MB faster-whisper model.
Choose one of these methods:

1. On the destination, use `--asr-model small --allow-network-models` once.
2. Separately copy an existing faster-whisper snapshot directory and pass its absolute
   destination path to `--asr-model`.

Do not rely on a model path under `/tmp`; use persistent storage on the destination.

### Fully offline destination

The current source archive alone is not a complete offline installer. Before moving to
a machine with no network access, also prepare:

- dependency wheels compatible with the destination OS, CPU architecture, and Python;
- the faster-whisper model snapshot; and
- the input video.

The `.venv` from this system is not a substitute for a compatible offline wheelhouse.
Native packages such as PyAV, CTranslate2, ONNX Runtime, and OpenCV must match the
destination platform.

### Compatibility boundary

The implementation and project package are complete, but deployment cannot be
guaranteed on an arbitrary host without knowing its operating system, CPU architecture,
Python version, available memory, and network policy. A Linux x86-64 system with Python
3.11 is the closest match to the verified environment.
