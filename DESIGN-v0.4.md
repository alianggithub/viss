# ViSS 0.4 Design — Output, Vision Routing, and Summary Enhancements

Version: 0.4.0  
Date: 2026-07-25  
Status: Implemented and tested

This document amends the ViSS 0.3 timestamp-frame design. Existing source-read-only,
semantic segmentation, transcript, evidence, and review contracts remain in force.

## 1. Source-adjacent defaults

If `--output` is absent, `analyze` MUST create `<source-stem>-viss-analysis` and
`dump-frames` MUST create `<source-stem>-timestamp-frames` in the resolved source
video's parent directory. `--output` MUST override the default. Output MUST remain in a
folder rather than loose beside the source. Source bytes MUST remain unchanged.

## 2. Annotated-only user timestamp frames

`dump-frames` MUST default to one retained image per request under `frames/`. That image
MUST contain the actual selected presentation timestamp and optional label. Temporary
raw material MUST be deleted after annotation. No `annotated/` folder may remain after
a successful default run.

The JSON/CSV/Markdown indexes MUST expose one canonical `frame_path`; JSON schema 1.1
records `output_mode=annotated_only`. `--raw-and-annotated` MAY restore schema-compatible
legacy raw/copy paths for older consumers. This change applies to user timestamp dumps;
automatic semantic-run representative frames keep their established v0.2 paths and
rerenderability.

## 3. Vision capability routing

ASR and transcript heuristics MUST NOT be misidentified as image-capable. With
`vision_recognition.mode=auto`, ViSS MUST query the configured OpenAI-compatible local
endpoint, confirm that it advertises the configured model, and use it for representative
frame descriptions. Unavailability MUST become a visible warning while analysis
continues. Mode `on` MUST make failure fatal; `off` MUST make no request.

The default fallback is `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8`. Requests MUST use
local image data URLs, deterministic temperature zero, configured timeouts, and record
model identity plus raw response. Parsed descriptions and relevance scores MUST be
stored in `evidence/vision-recognition.json`; a human view MUST be rendered as
`visual-descriptions.md`.

ViSS MUST NOT silently download or start the 12.6B model. The operator controls vLLM,
SGLang, or another compatible server because loading policy depends on GPU capacity,
quantization, licenses, caches, and other resident workloads. Automatic routing begins
once that server advertises the model.

## 4. Transcript-grounded whole-video summary

A completed analysis MUST produce `summary.json` and `summary.md` by default. The
summary MUST derive from semantic segment key points, which retain transcript evidence.
It MUST deduplicate normalized text and select points round-robin across segments before
adding second points, preventing early topics from consuming the whole budget.

JSON MUST record provider, grounding statement, segment IDs, timestamps, titles,
evidence references, confidence, chapter count, and key-point count. Markdown MUST show
an overview, timestamped key points, and chapter overview. Configuration MUST control
enablement, total points, per-segment points, topic count, and timestamp display.

The default summarizer is extractive and offline. It MUST NOT claim facts absent from
transcript evidence. Detailed per-segment `key-points.md` and the full transcript remain
unchanged.

## 5. Verification

Required tests cover source-adjacent default paths, explicit output override,
annotated-only cleanup and canonical paths, legacy two-set mode, model response parsing,
auto/on capability behavior, relevance propagation, visual-description rendering,
summary balance/deduplication/grounding, prior timestamp parsing/ranking, and all
original semantic-pipeline regressions.
