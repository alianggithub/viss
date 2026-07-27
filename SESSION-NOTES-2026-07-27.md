# Viss Session Notes — 2026-07-27

## Context
Processed two videos in `~/doc/tech/` using `video-semantic-segmenter` (ViSS) at three configurations for comparison.

## Videos
- `WeChatAppEx_IvcGyIgGt5.mp4` (45 MB) — 3 segments
- `WeChatAppEx_ObaVTlbeOk.mp4` (218 MB) — 19 segments

## Three Output Configurations (side-by-side in `~/doc/tech/`)

| Dir | Version | OCR | Vision | Segments |
|-----|---------|-----|--------|----------|
| `WeChatAppEx_IvcGyIgGt5/` | v0.2.0 | RapidOCR | — | 3 |
| `WeChatAppEx_IvcGyIgGt5-viss-analysis/` | v0.4.0 | RapidOCR | — | 3 |
| `WeChatAppEx_IvcGyIgGt5-viss-analysis-nemotron/` | v0.4.0 | RapidOCR | nemotron-nano-12b-v2-vl (NIM) | 3 |
| `WeChatAppEx_ObaVTlbeOk/` | v0.2.0 | RapidOCR | — | 19 |
| `WeChatAppEx_ObaVTlbeOk-viss-analysis/` | v0.4.0 | RapidOCR | — | 19 |
| `WeChatAppEx_ObaVTlbeOk-viss-analysis-nemotron/` | v0.4.0 | RapidOCR | nemotron-nano-12b-v2-vl (NIM) | 19 |

## Key Implementation Decisions

### 1. Annotated Frame Filename Convention (v0.4.0 patch)
**File**: `video-semantic-segmenter/src/vseg/frame_annotations.py` — `render_frame_annotations()`

**Before**: Frames written to `frames/annotated/` with original names (`segment-0001.jpg`). Index linked to `annotated/segment-0001.jpg`.

**After**: Single set of frames in `frames/` with scene-aware names:
```
0001__00-00-00-000__家比较.jpg
0002__00-00-01-200__#29.jpg
0003__00-01-32-267__128人.jpg
```
Format: `{index:04d}__{timestamp_hh-mm-ss-mmm}__{scene_slug}.jpg`

- No `annotated/` subfolder — only one frame set exists (the annotated one)
- `scene_slug()` sanitizes Unicode titles to path-safe strings
- `filename_timestamp()` converts `00:00:01.200` → `00-00-01-200`
- Index files (`index.json`, `index.md`, `index.csv`) reference these names directly

### 2. Nemotron Vision Model (not OCR)
- **RapidOCR** = actual OCR (onnxruntime), runs at step 6/9 "Reading on-screen text"
- **nemotron-nano-12b-v2-vl** = vision-language model (NVIDIA NIM), runs at step 8/9 "Running optional vision-capability fallback"
- Produces `visual-descriptions.md` and `evidence/vision-recognition.json` with natural-language frame descriptions
- Configured via `viss-nemotron-config.yaml`:
  ```yaml
  vision_recognition:
    mode: auto
    provider: openai_compatible
    endpoint: https://integrate.api.nvidia.com/v1
    model: nvidia/nemotron-nano-12b-v2-vl
    api_key: <NVAPI_KEY>
  ```

### 3. v0.4.0 Clean Install
- Unzipped `ViSS-v0.4.0-complete-2026-07-25.zip` → `~/workspace/video-semantic-segmenter-v0.4.0/`
- `uv sync --frozen --extra all --extra dev`
- Committed as clean baseline to `~/workspace/viss/` at tag `v0.4.0`
- Patch applied to `frame_annotations.py` in that repo

## Commands Used
```bash
# v0.4.0 + RapidOCR (default)
uv run vseg analyze ~/doc/tech/WeChatAppEx_IvcGyIgGt5.mp4 \
  --model small --allow-network-models --device auto

# v0.4.0 + nemotron vision
uv run vseg analyze ~/doc/tech/WeChatAppEx_IvcGyIgGt5.mp4 \
  --output ~/doc/tech/WeChatAppEx_IvcGyIgGt5-viss-analysis-nemotron \
  --config ~/doc/tech/viss-nemotron-config.yaml \
  --model small --allow-network-models --device auto
```

## Files to Preserve
- `~/doc/tech/viss-nemotron-config.yaml` — NIM endpoint + API key for nemotron vision
- `~/workspace/viss/video-semantic-segmenter/src/vseg/frame_annotations.py` — patched for scene-aware filenames
- All six output directories in `~/doc/tech/`

## Future Agent Notes
- Run `vseg annotate-frames <run_dir>` to regenerate annotated frames if needed (uses current code)
- The `annotated/` subfolder no longer exists in v0.4.0+patched; frames are directly in `frames/`
- Nemotron vision requires NIM API key inbound internet to `integrate.api.nvidia.com/v1`
- Three configs exist for A/B/C comparison — do not delete without explicit confirmation