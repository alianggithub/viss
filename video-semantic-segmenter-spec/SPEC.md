# Generic Video Semantic Segmenter — Implementation Specification

Version: 0.2  
Date: 2026-07-19  
Status: Implemented and verified  
Audience: junior implementation agents, reviewers, and test agents  
Evidence baseline: `../神奇美景在中国-宋春玲/poc-output/POC-REPORT.md`

## 1. Normative Language

The words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe
requirements. A task is incomplete when it violates a MUST/MUST NOT requirement,
even if its local tests pass.

When this specification conflicts with a task description, this specification
wins unless the task explicitly records an approved specification amendment.

## 2. Product Goal

Given a user-supplied video, produce:

1. variable-length semantic segments with start/end timestamps;
2. a concise title and key points for every segment;
3. the earliest meaningful representative frame for every segment;
4. a timestamp/scene annotated copy and index row for every representative frame;
5. a complete timestamped machine transcript; and
6. machine-readable evidence and confidence explaining each boundary and title.

A semantic segment is a contiguous portion of a video centered on one coherent
subject, location, attraction, activity, argument, procedure, or purpose. Its
duration is determined by content, not by a fixed time window.

## 3. Terminology

| Term | Definition |
|---|---|
| Frame | One decoded video image at a presentation timestamp. |
| Shot | Continuous visual footage between camera cuts. |
| Scene | One or more related shots in a visual situation. |
| Semantic segment | Variable-length interval devoted to one coherent topic. |
| Chapter | User-facing title and timestamp for a semantic segment. |
| Boundary candidate | Possible segment start supported by one or more signals. |
| Evidence | Transcript, audio, visual, embedded metadata, OCR, or user signal supporting a candidate. |
| Representative frame | Earliest clear and semantically relevant frame for a segment. |
| Annotated frame | Additive copy of a representative frame with a visible timestamp and optional scene title. |
| Frame index | JSON, CSV, or Markdown table mapping representative frames to timestamps and segments. |
| Run | One resumable analysis of one immutable source video. |

Shots and scenes MUST NOT automatically become semantic segments. One attraction
may contain dozens of cuts; a topic may also change without a visual cut.

## 4. Scope

### 4.1 Required for version 1

- Local MP4 input; architecture MUST allow other formats supported by the media
  decoder.
- Source probing, hashing, and embedded chapter/subtitle discovery.
- Timestamped multilingual speech transcription.
- Audit and targeted recovery of suspicious transcript gaps.
- Visual cut/fade candidate detection without saving every decoded frame.
- Opportunistic OCR for subtitles and title cards.
- Full-transcript semantic outlining, including long-video hierarchical analysis.
- Multimodal boundary candidate fusion and confidence.
- Representative-frame extraction from narrow search windows.
- Per-segment key points and complete transcript exports.
- Resumable, checkpointed execution.
- JSON, Markdown, SRT, VTT, and JPEG outputs.
- CPU-only operation; optional acceleration MAY be added behind interfaces.

### 4.2 Explicit non-goals for version 1

- Frame-perfect professional video editing.
- Guaranteed identification of unnamed locations from imagery alone.
- Human-quality verbatim transcription without review.
- Face recognition or identification of private individuals.
- Translation unless explicitly enabled.
- Destructive edits to the source video.
- Cloud upload by default.

### 4.3 Version 0.2 frame-annotation enhancement

- Preserve the stable canonical representative frame for each segment.
- Generate an additive annotated copy with a visible source timestamp and scene title.
- Give annotated copies readable filenames containing display order, timestamp, and
  a path-safe scene title.
- Produce equivalent JSON, CSV, and Markdown frame indexes.
- Regenerate annotation artifacts after title or representative-frame review changes.
- Retrofit a completed 0.1 run without rerunning ASR, OCR, or segmentation.
- Do not enumerate or persist every decoded source-video frame.

## 5. Prohibited POC Coupling

Production code MUST NOT contain:

- the source filename `神奇美景在中国-宋春玲`;
- fixed timestamps learned from that video;
- hard-coded attraction or farming-method lists;
- a universal assumption that topics begin with `去了…才知道…`;
- a universal assumption that topics begin with `这是什么养殖方式`;
- manual corrections embedded in generic algorithms; or
- absolute `/nobackup/chrgu/test/...` paths.

Phrase-pattern detectors MAY exist as a generic pluggable signal. Their output
MUST be treated as evidence, not as the final segmentation algorithm.

## 6. Command-Line Contract

The executable name is `vseg`.

```text
vseg analyze INPUT --output OUTPUT_DIR [options]
vseg resume RUN_DIR
vseg validate RUN_DIR
vseg render RUN_DIR [--format markdown|json|srt|vtt]
vseg annotate-frames RUN_DIR
```

Minimum `analyze` options:

```text
--language auto|LANGUAGE_CODE
--asr-model MODEL_ID
--semantic-provider PROVIDER_NAME
--ocr auto|on|off
--device auto|cpu|cuda
--config PATH
--force-new-run
```

Behavior:

- `INPUT` MUST remain unmodified.
- `OUTPUT_DIR` MUST be created if absent.
- Without `--force-new-run`, the tool MUST resume a matching incomplete run
  rather than silently duplicate it.
- A run is matched by source content hash plus normalized effective config.
- Human-readable progress goes to stderr; primary requested data goes to files.
- Exit code 0 means required outputs validated successfully.
- Exit code 2 means invalid arguments/configuration.
- Exit code 3 means source cannot be read or decoded.
- Exit code 4 means a required model/provider is unavailable.
- Exit code 5 means analysis completed partially and requires review/retry.
- Exit code 6 means output validation failed.

## 7. Output Contract

```text
OUTPUT_DIR/
├── run.json
├── source.json
├── config.effective.yaml
├── transcript/
│   ├── transcript.json
│   ├── transcript.md
│   ├── transcript.txt
│   ├── transcript.srt
│   └── transcript.vtt
├── evidence/
│   ├── audio-events.json
│   ├── visual-events.json
│   ├── ocr-events.json
│   └── boundary-candidates.json
├── segments.json
├── chapters.md
├── key-points.md
├── frames/
│   ├── <segment-id>.jpg
│   ├── annotated/
│   │   └── <index>__<timestamp>__<scene-title>.jpg
│   ├── index.json
│   ├── index.csv
│   └── index.md
├── checkpoints/
│   └── <stage>.json
└── logs/
    └── run.jsonl
```

Rules:

- Paths inside manifests MUST be relative to the run directory.
- All stored timestamps MUST use seconds from source-media time zero as decimal
  numbers. Renderers MAY additionally display `HH:MM:SS.mmm`.
- JSON MUST be UTF-8 and MUST preserve original-language text.
- Rerunning a completed stage with identical inputs MUST be idempotent.
- No output file may claim “human verified” unless a human review event exists.
- The source hash and config hash MUST appear in `run.json`.
- Canonical `frames/<segment-id>.jpg` paths MUST remain stable for compatibility.
- Every representative frame MUST have exactly one frame-index row when annotation is
  enabled.
- Annotated filenames MUST be path-safe, bounded below filesystem component limits,
  and preserve readable Unicode when supported.

## 8. Architecture

```text
Source probe
   |
   +--> embedded chapters/subtitles -------------------+
   |                                                   |
   +--> audio decode --> ASR --> gap audit/recovery ---+-->
   |                                                   |   candidate fusion
   +--> visual metrics --> cuts/fades -----------------+          |
   |                                                   |          v
   +--> selective frames --> OCR/title cards ----------+   semantic segments
                                                               |
                                       +-----------------------+------------------+
                                       |                       |                  |
                                  key points           representative frame   renderers
                                                               |
                                                     annotation + frame index
```

Every box MUST expose a module interface and write a checkpoint. An implementation
MUST be able to replace ASR, OCR, semantic-analysis, and frame-ranking providers
without rewriting orchestration.

## 9. Required Module Interfaces

Names are conceptual; exact language syntax may vary.

```python
class MediaProbe:
    def probe(source_path) -> SourceMetadata: ...

class Transcriber:
    def transcribe(audio_ref, options) -> Transcript: ...
    def transcribe_interval(audio_ref, start, end, options) -> Transcript: ...

class AudioEventDetector:
    def detect(audio_ref) -> list[AudioEvent]: ...

class VisualEventDetector:
    def detect(video_ref) -> list[VisualEvent]: ...

class OcrProvider:
    def recognize(frame) -> list[TextObservation]: ...

class SemanticAnalyzer:
    def outline(transcript, context) -> SemanticOutline: ...
    def refine_boundary(left, right, nearby_evidence) -> BoundaryDecision: ...
    def summarize(segment_context) -> SegmentSummary: ...

class FrameSelector:
    def select(segment, candidate_frames, context) -> FrameDecision: ...
```

Provider results MUST include provider name/version, parameters, confidence when
available, and errors/warnings.

## 10. Pipeline Stages

### 10.1 Stage A — Ingest and probe

The stage MUST:

1. validate that the source is a regular readable file;
2. calculate SHA-256 without modifying the source;
3. record container, streams, codecs, duration, dimensions, frame rate/time base,
   rotation, start times, and variable-frame-rate indicators;
4. enumerate embedded chapters and subtitle streams;
5. reject zero-duration or undecodable video with a clear error; and
6. normalize display orientation for later frame analysis.

Embedded chapters are evidence, not automatically trusted truth. Embedded
subtitles SHOULD be preferred over ASR when their language/content matches audio,
but both sources SHOULD remain traceable.

### 10.2 Stage B — Audio preparation

The decoder SHOULD feed audio directly to ASR when supported. If normalization is
required, create a temporary lossless mono PCM/WAV representation at the ASR
model's expected rate.

MP3 generation MUST NOT be required. It MAY be an optional user export. Re-encoding
to lossy MP3 before ASR SHOULD be avoided.

### 10.3 Stage C — Complete transcript

The transcriber MUST produce:

- detected/requested language;
- ordered segments with start/end/text;
- word timing when the provider supports it;
- confidence/probability metadata when available;
- no-speech and other diagnostic values when available; and
- explicit gaps rather than invented text.

The raw transcript MUST remain immutable after creation. Corrected display text,
OCR alternatives, and human edits MUST be stored as derived annotations.

Word timestamps are estimates and MUST be labeled accordingly.

### 10.4 Stage D — Transcript gap audit

The gap auditor MUST find suspicious intervals using at least:

- transcript gaps longer than a configurable threshold;
- audio energy or speech probability inside the gap;
- OCR text changes or active subtitle text;
- visual activity inconsistent with an ending; and
- abrupt differences between text immediately before/after the gap.

For suspicious gaps, run interval transcription with alternate settings such as
disabled/relaxed VAD, overlap, or a stronger model. Recovered text MUST record
which pass produced it. Results MUST be merged without duplicating overlapping
words.

### 10.5 Stage E — Visual-event detection

The visual detector MUST process decoded frames or compact frame metrics without
saving every frame. It SHOULD detect:

- hard cuts;
- fades/dissolves when feasible;
- black/near-black intervals;
- large composition changes; and
- title-card-like stable text screens.

It MAY downscale frames for metrics. It MUST retain original presentation
timestamps and MUST handle variable frame rate.

Visual cuts are low-level evidence. They MUST NOT directly define chapters.

### 10.6 Stage F — OCR observations

OCR SHOULD run selectively on:

- frames near transcript topic candidates;
- title-card candidates;
- frames where persistent subtitle regions are detected; and
- representative-frame candidates when text may identify the subject.

The OCR provider MUST return text, bounding polygon, confidence, timestamp, and
model identity. Observations across nearby frames SHOULD be deduplicated.

OCR MUST NOT silently replace ASR text. Store alternatives and agreement status.
Proper nouns SHOULD be resolved from agreement among ASR, OCR, semantic context,
and optional human review.

### 10.7 Stage G — Global semantic outline

The semantic analyzer MUST understand the whole video's structure before final
boundaries are committed.

For transcripts that exceed provider context limits:

1. divide transcript by sentence/ASR boundaries into overlapping time chunks;
2. generate chunk-level topics and transition candidates;
3. create a global outline from the chunk summaries;
4. reconcile overlapping candidates; and
5. refine boundaries using original nearby transcript, never summaries alone.

The outline MUST allow variable-length segments. Fixed windows MAY organize model
input but MUST NOT become final segment boundaries.

The analyzer SHOULD identify introductions, conclusions, advertisements,
compilation joins, and repeated topic structures as first-class segment types.

### 10.8 Stage H — Boundary candidate fusion

Each candidate MUST retain independent evidence such as:

```text
transcript_topic_change
transition_phrase
long_pause
speaker_change
music_or_audio_change
hard_visual_cut
fade_or_black_interval
title_card_change
ocr_proper_noun_change
embedded_chapter
user_marker
```

Candidate scoring MUST be configurable and versioned. A default decision SHOULD
give semantic transcript evidence more weight than a single visual cut for
spoken informational videos.

Nearby candidates within a configurable merge window SHOULD be clustered. The
final timestamp SHOULD be selected from the strongest local evidence, refined to
a nearby word/sentence, pause, title card, or visual transition.

Minimum/maximum segment durations MAY be soft warnings. They MUST NOT force the
merging or splitting of clearly coherent content solely to meet duration limits.

### 10.9 Stage I — Segment title and key points

For each final segment, generate:

- concise title in the video's primary language;
- optional normalized/translated title when configured;
- 1–5 factual key points grounded in transcript/OCR/visual evidence;
- source spans or timestamps supporting each key point;
- confidence and unresolved proper-name alternatives; and
- segment type.

Summaries MUST NOT introduce facts absent from the source evidence. Low-evidence
segments MUST say so rather than hallucinate a description.

### 10.10 Stage J — Representative-frame selection

Search a configurable window beginning at the segment boundary. Do not save every
frame. Use staged filtering:

1. sample inexpensive candidates (for example 2–4 fps within the window);
2. reject black, near-white, low-contrast, blurred, corrupted, or transition
   frames;
3. penalize player controls, large unrelated overlays, and duplicate frames;
4. score semantic relevance against segment title/transcript using a pluggable
   vision provider when available; and
5. choose the earliest candidate meeting both quality and relevance thresholds.

If none passes, choose the best-scoring fallback and mark `needs_review=true`.
The decision MUST record candidate scores and why the winner was chosen.

“First meaningful” means earliest acceptable and relevant, not literal first
decoded frame and not simply the visually prettiest frame.

### 10.11 Stage K — Frame annotation and indexing

For each representative frame, the renderer MUST:

1. retain the canonical `frames/<segment-id>.jpg`;
2. create an annotated copy under `frames/annotated/`;
3. overlay `HH:MM:SS.mmm` and, when enabled, the semantic-segment title;
4. derive a filename from display order, timestamp, and normalized scene title;
5. emit one consistent row to `index.json`, `index.csv`, and `index.md`; and
6. remove stale annotated copies before a deterministic rerender.

The index row MUST include display index, segment ID/title/boundaries, precise frame
timestamp in seconds and display form, approximate source frame number when average
FPS is available, canonical and annotated paths, selection quality/reason, and review
state. The approximate frame number is informational; the presentation timestamp is
authoritative, especially for variable-frame-rate media.

Unicode titles SHOULD remain readable. Reserved path characters, control characters,
excess whitespace, and overlong UTF-8 names MUST be normalized safely. Overlay
rendering SHOULD use a configured font, then a CJK-capable system font, then a safe
fallback.

`vseg annotate-frames RUN_DIR` MUST perform this stage alone on a completed run. A
pre-0.2 run without annotation configuration MUST remain valid until explicitly
retrofitted.

### 10.12 Stage L — Rendering and validation

Render chapters, key points, transcript formats, and frames only from validated
manifests. Validation MUST confirm:

- segments are ordered, non-overlapping, and cover intended source intervals;
- `0 <= start < end <= source_duration + tolerance`;
- IDs and paths are unique;
- every referenced frame exists;
- annotation index counts and annotated frame paths agree when annotation is enabled;
- transcript cues are time ordered;
- output JSON matches its schema; and
- incomplete/review states are clearly visible.

## 11. Data Model

### 11.1 `run.json`

Required fields:

```json
{
  "schema_version": "1.0",
  "run_id": "uuid",
  "source_sha256": "hex",
  "config_sha256": "hex",
  "status": "running|partial|needs_review|complete|failed",
  "created_at": "RFC3339 UTC",
  "updated_at": "RFC3339 UTC",
  "completed_stages": [],
  "warnings": [],
  "software_versions": {}
}
```

### 11.2 Semantic segment

```json
{
  "id": "seg-0001",
  "start_s": 10.07,
  "end_s": 14.71,
  "type": "topic",
  "title": "Example attraction",
  "title_language": "zh",
  "title_confidence": 0.94,
  "title_alternatives": [],
  "key_points": [
    {
      "text": "Grounded statement",
      "evidence_refs": ["transcript-word-10:42"],
      "confidence": 0.91
    }
  ],
  "boundary": {
    "confidence": 0.90,
    "algorithm_version": "boundary-fusion-v1",
    "evidence_refs": ["candidate-123"],
    "needs_review": false
  },
  "representative_frame": {
    "path": "frames/seg-0001.jpg",
    "timestamp_s": 10.43,
    "quality_score": 0.89,
    "relevance_score": 0.92,
    "selection_reason": "earliest candidate above thresholds",
    "needs_review": false
  },
  "transcript_span_refs": ["transcript-segment-2"]
}
```

Confidence values MUST be in `[0, 1]` or `null` when a provider has no meaningful
calibration. Invented precision is prohibited.

### 11.3 Boundary candidate

```json
{
  "id": "candidate-123",
  "timestamp_s": 10.07,
  "source": "transcript",
  "kind": "transition_phrase",
  "raw_score": 0.93,
  "normalized_score": 0.88,
  "provider": "provider-name/version",
  "payload": {},
  "cluster_id": "cluster-12"
}
```

### 11.4 `frames/index.json`

```json
{
  "schema_version": "1.0",
  "frame_count": 1,
  "frames": [
    {
      "index": 1,
      "segment_id": "seg-0001",
      "scene_title": "Example attraction",
      "segment_start_s": 10.07,
      "segment_end_s": 14.71,
      "frame_timestamp_s": 10.43,
      "frame_timestamp": "00:00:10.430",
      "source_frame_number_estimate": 313,
      "original_path": "frames/seg-0001.jpg",
      "annotated_path": "frames/annotated/0001__00-00-10-430__Example-attraction.jpg",
      "annotated_filename": "0001__00-00-10-430__Example-attraction.jpg",
      "quality_score": 0.89,
      "selection_reason": "earliest candidate above thresholds",
      "needs_review": false
    }
  ]
}
```

`index.csv` MUST expose the same fields as tabular columns. `index.md` MUST contain
a human-readable table with working relative links to annotated images.

## 12. Checkpointing and Idempotency

Stages use this state model:

```text
pending -> running -> complete
                   -> needs_review
                   -> retryable_failure
                   -> permanent_failure
```

Each checkpoint MUST include input hashes, effective stage configuration,
provider versions, output paths, status, and error details. A checkpoint may be
reused only when all relevant hashes and versions match.

Per-segment OCR, summary, and frame selection MUST checkpoint independently so a
long video does not lose completed work after interruption.

Temporary files MUST be written to a staging name and atomically renamed after
validation.

## 13. Configuration

Minimum configuration structure:

```yaml
runtime:
  device: auto
  workers: 2

transcription:
  provider: faster_whisper
  model: small
  language: auto
  word_timestamps: true
  vad: true
  suspicious_gap_s: 8.0

visual:
  detector: adaptive
  analysis_width: 320

ocr:
  mode: auto
  provider: rapidocr
  max_frames_per_minute: 30

semantic:
  provider: configured_provider
  chunk_duration_s: 600
  chunk_overlap_s: 30
  candidate_merge_s: 2.0

frame_selection:
  search_window_s: 8.0
  sample_fps: 3.0
  min_quality: 0.55
  min_relevance: 0.55

frame_annotation:
  enabled: true
  overlay_timestamp: true
  overlay_scene_title: true
  scene_aware_filenames: true
  font_path: null
  font_size_ratio: 0.042
  jpeg_quality: 92
  max_scene_filename_chars: 64

privacy:
  allow_network_models: false
  retain_temporary_audio: false
```

Secrets MUST NOT be placed in this file. Unknown keys SHOULD fail validation to
catch agent typos.

## 14. Privacy and Security

- Local-only processing MUST be the default.
- Any provider that uploads audio, frames, transcript, or metadata MUST require
  explicit configuration and MUST be disclosed in `run.json`.
- Logs MUST NOT contain full raw media, credentials, or unbounded transcript
  dumps.
- Input filenames and transcript content may be sensitive and SHOULD not appear
  in telemetry.
- Temporary decoded audio/frames MUST be deleted according to retention config.
- Paths MUST be normalized; output writes MUST remain under the requested run
  directory.
- Model downloads MUST be pinned/versioned and must not occur during unit tests.

## 15. Performance Requirements

The implementation MUST be streaming or bounded-memory with respect to video
duration. It MUST NOT retain all full-resolution decoded frames in memory.

Version 1 CPU target for a 10-minute 1080p or smaller video:

- no more than 2 GiB application peak memory, excluding model memory;
- no more than one canonical and one annotated representative JPEG per final segment
  plus explicitly enabled diagnostics;
- resumable progress at least once per pipeline stage and per semantic segment;
- performance metrics recorded per stage.

These are engineering targets, not acceptance claims until benchmarked.

## 16. Logging and Observability

JSONL log events MUST include timestamp, run ID, stage, event, severity, and
structured fields. Do not use free-form logs as the only record of state.

Record at least:

- stage start/end and elapsed time;
- provider/model identity;
- decoded duration and frame count/metric count;
- ASR language and gaps;
- boundary candidate and final segment counts;
- OCR attempted/succeeded counts;
- frame candidate/rejection counts;
- retries, warnings, and review reasons; and
- peak memory when available.

## 17. Testing Strategy

### 17.1 Unit tests

Unit tests MUST use tiny local fixtures or mocks and cover:

- timestamp conversion and variable-frame-rate handling;
- transcript overlap merge and gap detection;
- candidate clustering/fusion;
- segment ordering/coverage validation;
- OCR observation deduplication;
- frame quality filters;
- checkpoint hash invalidation;
- renderer escaping for multilingual text; and
- path containment/security.

### 17.2 Integration fixtures

Maintain legal, small fixtures for:

- explicit repeated transition phrases;
- implicit spoken topic changes;
- frequent visual cuts within one topic;
- topic change without a cut;
- long silence with and without speech missed by VAD;
- title cards/subtitles;
- no speech/music-heavy footage;
- multilingual speech;
- variable frame rate and rotated video; and
- corrupt/truncated input.

### 17.3 Human-labeled evaluation

Each evaluation video requires reference annotations:

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

Report:

- topic precision, recall, and F1;
- median and 90th-percentile boundary error;
- title/proper-name accuracy;
- representative-frame acceptance rate;
- transcript word/character error rate when reference text exists;
- runtime and peak memory; and
- review rate.

## 18. Version 1 Acceptance Gates

The generic implementation is acceptable only when all gates pass:

1. No prohibited POC coupling is present (`rg` check plus review).
2. A clean install exposes the documented CLI.
3. Source files remain byte-identical after processing.
4. Interrupted processing resumes without duplicating completed work.
5. JSON schema validation and all unit tests pass.
6. Three human-labeled videos are evaluated:
   - explicit narrated transitions;
   - implicit narrated transitions; and
   - lightly narrated/music-heavy content.
7. Across those evaluation videos:
   - major-topic recall is at least 0.80;
   - major-topic precision is at least 0.75;
   - median accepted-boundary error is at most 10 seconds;
   - at least 0.80 of representative frames are accepted without replacement;
   - no low-confidence proper name is silently presented as certain.
8. All required outputs are produced with no broken references.
9. Privacy/network behavior is documented and defaults to local-only.
10. A reviewer can adjust a title, boundary, and frame without editing raw
    provider artifacts.

Thresholds may be revised only from measured evaluation evidence.

## 19. Junior-Agent Change Rules

Junior agents MUST:

- implement only their assigned task and direct prerequisites;
- preserve public schemas and interfaces unless the task authorizes a change;
- add tests for every behavior change;
- use dependency injection/mocks rather than downloading models in unit tests;
- never embed test-video names, timestamps, or corrections in production code;
- keep source media immutable;
- record assumptions and unresolved questions in their handoff; and
- stop and request review when a schema/interface conflict would affect other
  tasks.

## 20. Reference Implementations and Documentation

- OpenAI Whisper: <https://github.com/openai/whisper>
- faster-whisper: <https://github.com/SYSTRAN/faster-whisper>
- PyAV: <https://pyav.org/docs/stable/>
- RapidOCR: <https://github.com/RapidAI/RapidOCR>
- PySceneDetect: <https://www.scenedetect.com/docs/latest/api.html>
- FFmpeg filters: <https://ffmpeg.org/ffmpeg-filters.html>
- ffprobe: <https://ffmpeg.org/ffprobe.html>

Dependencies MUST be pinned after selection. A reference here is not permission
to couple public interfaces directly to one library.
