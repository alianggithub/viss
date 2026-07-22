# Generic Video Semantic Segmenter — Junior-Agent Task Backlog

Version: 0.2  
Companion specification: `SPEC.md`  
Task size target: approximately 0.5–2 focused engineering days per task

## 1. How Agents Must Use This Backlog

Before starting a task, an agent must:

1. read `SPEC.md` completely;
2. read the selected task and every dependency's handoff;
3. inspect existing repository instructions and tests;
4. confirm that no other active task owns the same files; and
5. state assumptions before changing a public interface.

An agent owns only the files listed in its task plus tests directly associated
with those files. If implementation requires changing another task's public
contract, stop and request integration-owner review.

Every handoff must report:

- files changed;
- behavior implemented;
- tests run and exact results;
- assumptions made;
- limitations or follow-up work;
- schema/interface changes; and
- whether source media or network access was used.

No agent may claim success from an ad-hoc command alone. Required automated tests
and acceptance checks must pass.

## 2. Dependency Graph

```text
T00 Scaffold
 |
 +--> T01 Contracts/Schemas ----+---------------------------+
 |                              |                           |
 +--> T02 Media Probe ----------+--> T06 Visual Events      |
 |                              |                           +--> T12 Frame Selector
 +--> T03 Checkpoint Runtime ---+---------------------------+          |
 |                              |                                      |
 +--> T04 ASR Provider --> T05 Gap Audit --> T09 Semantic Outline      |
 |             |                         \              |              |
 |             +--> T07 OCR -------------+----------> T10 Fusion ------+
 |                                                       |
 |                                                       +--> T11 Titles/Key Points
 |                                                                  |
 +--> T15 Evaluation Harness ---------------------------------------+
                                                                    |
 T13 Render/Validate <-----------------------------------------------+
        |
 T14 CLI/Orchestration
        |
 T16 End-to-End Integration --> T17 Review Overrides --> T18 Packaging/Docs
```

Tasks whose dependencies are satisfied may run in parallel if their owned files
do not overlap.

## 3. Repository Target Layout

Agents should converge on:

```text
video-semantic-segmenter/
├── pyproject.toml
├── README.md
├── uv.lock
├── src/vseg/
│   ├── cli.py
│   ├── config.py
│   ├── contracts.py
│   ├── pipeline.py
│   ├── checkpoints.py
│   ├── probe.py
│   ├── transcript.py
│   ├── gap_audit.py
│   ├── audio_events.py
│   ├── visual_events.py
│   ├── ocr.py
│   ├── semantic.py
│   ├── boundary_fusion.py
│   ├── frame_selector.py
│   ├── summarize.py
│   ├── render.py
│   └── validate.py
├── schemas/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── evaluation/
```

Changes to this layout are allowed only when recorded in the integration handoff.

## 4. Global Definition of Done

A task is done only when:

- formatting, lint, type checks, and relevant tests pass;
- tests require no network and no model download;
- new behavior has deterministic fixtures or mocks;
- public functions have docstrings/types;
- errors are structured and actionable;
- source media remains immutable;
- no POC filename, timestamp, attraction, phrase, or absolute path is embedded in
  production code; and
- the task handoff is complete.

## 5. Foundation Tasks

### T00 — Project scaffold and quality tooling

**Dependencies:** none  
**Can run in parallel:** no; first task  
**Owned files:** `pyproject.toml`, lock file, base package/init, test configuration,
lint/type configuration, `.gitignore`, initial `README.md`

**Goal:** Create a reproducible Python 3.11+ project with a working empty CLI and
test suite.

**Implementation requirements:**

- Package name: `vseg`.
- Expose `vseg --help` through a console-script entry point.
- Pin direct dependencies and commit a lock file.
- Add pytest, formatter/linter, and type checker commands.
- Keep heavy providers optional through extras such as `asr`, `ocr`, and `dev`.
- Ignore model caches, source media, run outputs, and credentials.

**Tests:**

- import package;
- invoke `vseg --help` and verify exit code 0;
- verify supported Python version metadata.

**Acceptance:** A clean environment can install the locked project and run the
empty test suite without downloading ASR/OCR models.

**Out of scope:** Any media processing.

### T01 — Contracts, schemas, and configuration

**Dependencies:** T00  
**Can run in parallel:** no; contracts unblock most tasks  
**Owned files:** `contracts.py`, `config.py`, `schemas/*`, contract/config tests

**Goal:** Implement typed domain objects and JSON schemas matching `SPEC.md`.

**Deliverables:**

- types for source metadata, transcript segments/words, audio/visual/OCR events,
  boundary candidates, semantic segments, frames, checkpoints, and run state;
- schema-version constants;
- strict YAML configuration loader with defaults and unknown-key rejection;
- canonical config serialization and SHA-256 calculation;
- JSON schema files for `run.json`, transcript, candidates, and `segments.json`.

**Tests:**

- valid example round trips;
- invalid confidence, timestamp, enum, path, and unknown config keys fail;
- canonical config hashes are stable despite YAML key order;
- multilingual strings remain unchanged.

**Acceptance:** Every JSON example in `SPEC.md` validates, and malformed variants
fail with field-specific errors.

**Out of scope:** Provider implementations and persistence orchestration.

### T02 — Media probe and timestamp normalization

**Dependencies:** T00, T01  
**Can run in parallel:** yes, with T03/T04/T15  
**Owned files:** `probe.py`, media-probe tests/fixtures

**Goal:** Safely inspect source media without modifying it.

**Deliverables:**

- streaming SHA-256 calculation;
- PyAV-backed probe provider behind `MediaProbe`;
- container/stream metadata, duration, time bases, frame rate, rotation, embedded
  chapters, and subtitle stream inventory;
- timestamp normalization to media time zero;
- structured errors for missing, truncated, zero-duration, and undecodable input.

**Tests:**

- tiny constant-frame-rate fixture;
- variable-frame-rate fixture;
- rotated fixture;
- embedded chapter/subtitle fixture;
- truncated fixture;
- source hash before/after remains identical.

**Acceptance:** Fixture metadata matches expected JSON within documented numeric
tolerances; source bytes never change.

### T03 — Run state, checkpointing, and evidence persistence

**Dependencies:** T00, T01  
**Can run in parallel:** yes  
**Owned files:** `checkpoints.py`, persistence helpers, checkpoint tests

**Goal:** Provide atomic, resumable, hash-aware stage and per-segment checkpoints.

**Deliverables:**

- run-directory creator and containment checks;
- atomic JSON writes using temporary file plus rename;
- checkpoint state transitions from `SPEC.md`;
- reuse/invalidation by source hash, config hash, provider version, and stage input;
- per-segment checkpoint keys;
- JSONL structured event logger.

**Tests:**

- simulated interruption after N segments resumes at N+1;
- identical rerun performs no duplicate work;
- changed config/provider invalidates only affected stages;
- corrupt checkpoint is rejected without destroying other checkpoints;
- path traversal outside run directory is blocked.

**Acceptance:** An integration test kills a fake stage midway, resumes it, and
produces exactly one output per item.

## 6. Media and Evidence Tasks

### T04 — Transcription provider and transcript renderers

**Dependencies:** T00, T01, T02  
**Can run in parallel:** yes, with T03/T06/T15  
**Owned files:** `transcript.py`, ASR provider adapter, transcript tests

**Goal:** Implement complete and interval transcription behind `Transcriber`.

**Deliverables:**

- faster-whisper adapter with injected model factory;
- language auto-detection or requested-language support;
- segment and optional word timestamps/confidence diagnostics;
- complete and interval transcription calls;
- deterministic transcript merge utility for overlapping passes;
- Markdown, text, SRT, and VTT rendering from the transcript contract.

**Tests:**

- fake provider outputs; no real model download;
- overlapping interval merge without duplicated words;
- punctuation/multilingual rendering;
- empty/silent audio behavior;
- invalid/non-monotonic provider timestamps are rejected.

**Acceptance:** Mocked complete and interval passes produce schema-valid,
chronological JSON/SRT/VTT with stable output.

**Out of scope:** Deciding which gaps require interval retranscription (T05).

### T05 — Transcript gap audit and targeted recovery

**Dependencies:** T03, T04, T06 event contract  
**Can run in parallel:** after dependencies  
**Owned files:** `gap_audit.py`, `audio_events.py`, gap-audit tests

**Goal:** Detect suspicious transcript gaps and recover omitted speech.

**Deliverables:**

- audio-energy/speech-activity event interface;
- configurable suspicious-gap detector;
- evidence from gap length, audio activity, OCR/visual activity, and adjacent text;
- targeted retranscription job requests with relaxed/no VAD and overlap;
- provenance-preserving transcript merge;
- review warning when recovery remains uncertain.

**Tests:**

- true silence is not retranscribed repeatedly;
- speech inside a long ASR gap triggers one interval job;
- recovered overlap does not duplicate boundary words;
- failed recovery becomes `needs_review`, not fabricated silence.

**Acceptance:** A fixture modeled after the POC's missed compilation transition is
recovered using mocks without embedding its text or timestamp.

### T06 — Visual-event detector

**Dependencies:** T01, T02  
**Can run in parallel:** yes  
**Owned files:** `visual_events.py`, visual-event fixtures/tests

**Goal:** Generate timestamped low-level visual evidence using bounded memory.

**Deliverables:**

- streaming/downscaled frame analysis;
- hard-cut, fade/black, and composition-change event adapters;
- PySceneDetect adapter or equivalent behind `VisualEventDetector`;
- event normalization and deduplication;
- optional diagnostic metrics without persisting every source frame.

**Tests:**

- synthetic cut, fade, and no-cut clips;
- rapid camera motion does not produce unbounded duplicate events;
- variable-frame-rate timestamps remain correct;
- memory test verifies frames are released.

**Acceptance:** Expected events are detected within fixture tolerance and no JPEGs
are emitted unless diagnostics are explicitly enabled.

**Out of scope:** Treating cuts as chapters.

### T07 — Selective OCR evidence provider

**Dependencies:** T01, T02, T03  
**Can run in parallel:** yes  
**Owned files:** `ocr.py`, OCR scheduling/deduplication tests

**Goal:** Extract supporting text only from selected frames.

**Deliverables:**

- RapidOCR adapter behind `OcrProvider` with injected engine;
- frame/time/bounding-box/text/confidence observations;
- nearby-frame text deduplication;
- crop-region support for persistent subtitle bands;
- scheduling API accepting boundary/title-card/frame candidates;
- `off`, `on`, and `auto` behavior.

**Tests:**

- mocked Chinese/English OCR observations;
- one-character alternatives remain separate, not silently corrected;
- repeated subtitle across frames deduplicates with time span;
- OCR-disabled mode imports no heavy provider dependency.

**Acceptance:** OCR observations preserve raw provider text and model identity and
never mutate the raw transcript.

## 7. Semantic Analysis Tasks

### T08 — Transcript context builder and hierarchical chunking

**Dependencies:** T01, T04  
**Can run in parallel:** yes, before T09  
**Owned files:** semantic context/chunk utilities and tests

**Goal:** Prepare long transcripts for global reasoning without turning fixed
chunks into chapters.

**Deliverables:**

- sentence/ASR-boundary chunker with time overlap;
- token/character budget abstraction independent of one LLM vendor;
- chunk summaries with source-span references;
- global-outline input assembled from summaries;
- original-context retrieval around any proposed boundary.

**Tests:**

- long synthetic transcript chunks deterministically;
- every source span is covered;
- overlap reconciliation has no missing sentences;
- final boundaries remain tied to original timestamps, not summary positions.

**Acceptance:** A transcript larger than a fake provider context window produces a
complete traceable hierarchy.

### T09 — Semantic outline provider

**Dependencies:** T03, T08  
**Can run in parallel:** no with T10 on same interface  
**Owned files:** `semantic.py`, provider adapters/prompts, semantic tests

**Goal:** Propose global topics and transcript-based boundary candidates without
video-specific phrases.

**Deliverables:**

- `SemanticAnalyzer` provider protocol and one configured implementation;
- structured prompt/request and schema-validated response;
- chunk topic extraction, global outline, introduction/outro/ad detection;
- original-context boundary refinement;
- low-confidence/invalid response handling;
- optional generic transition-phrase evidence plugin, disabled from being final
  authority.

**Tests:**

- mocked provider responses for explicit and implicit transitions;
- malformed provider JSON retries then becomes reviewable failure;
- repeated visual cuts do not split one transcript topic;
- prompt contains no POC-specific phrase, name, or timestamp.

**Acceptance:** Given fixture transcripts, produces schema-valid semantic topic
candidates with evidence references and variable durations.

### T10 — Multimodal candidate fusion and final boundaries

**Dependencies:** T05, T06, T07, T09  
**Can run in parallel:** no; integration point  
**Owned files:** `boundary_fusion.py`, fusion tests

**Goal:** Cluster multimodal evidence and create ordered, confidence-aware final
segment intervals.

**Deliverables:**

- configurable score normalization by evidence source;
- temporal clustering within merge window;
- semantic-first defaults for spoken informational videos;
- timestamp refinement to nearby word, pause, title card, or visual event;
- introduction/outro/compilation-join support;
- coverage/overlap reconciliation;
- algorithm version and score explanation.

**Tests:**

- many cuts inside one topic remain one segment;
- semantic change without a cut still creates a boundary;
- transcript and title-card candidates near each other merge;
- ambiguous clusters produce `needs_review`;
- short valid topics are not merged solely by duration.

**Acceptance:** All integration fixtures produce ordered, non-overlapping segments
and retain every contributing evidence reference.

### T11 — Grounded titles and key points

**Dependencies:** T07, T09, T10  
**Can run in parallel:** yes, with T12  
**Owned files:** `summarize.py`, summary tests

**Goal:** Generate concise titles and 1–5 grounded key points per segment.

**Deliverables:**

- evidence bundle builder for each segment;
- title/key-point provider request and schema validation;
- ASR/OCR proper-name agreement and alternative tracking;
- confidence/review rules;
- evidence references for every key point;
- no-evidence fallback.

**Tests:**

- OCR and ASR agreement raises confidence;
- one-character disagreement remains an alternative;
- low evidence returns a review state, not invented facts;
- all key points reference source evidence.

**Acceptance:** Fixture outputs contain no unsupported statement and uncertain
proper nouns are visibly uncertain.

## 8. Frame, Output, and Orchestration Tasks

### T12 — Representative-frame selector

**Dependencies:** T02, T03, T10, T11 title contract  
**Can run in parallel:** yes, with T11 using agreed contracts  
**Owned files:** `frame_selector.py`, frame tests/fixtures

**Goal:** Select the earliest technically acceptable and semantically relevant
frame for each segment without dumping all frames.

**Deliverables:**

- narrow-window sampler with configurable fps;
- brightness, contrast, sharpness, corruption, overlay, and duplicate metrics;
- pluggable semantic relevance scorer;
- earliest-above-threshold selection;
- best fallback plus `needs_review` when none passes;
- candidate score/rejection diagnostics;
- one final JPEG per segment using atomic writes.

**Tests:**

- black/fade/blur frames rejected;
- first clear but irrelevant frame loses to later relevant frame;
- earliest of two passing relevant frames wins;
- no candidate produces reviewable fallback;
- exactly one referenced JPEG per final segment.

**Acceptance:** Labeled frame fixtures achieve at least 80% automatic acceptance
before end-to-end evaluation.

### T13 — Output renderers and validator

**Dependencies:** T01, T04, T10, T11, T12  
**Can run in parallel:** after contracts stabilize  
**Owned files:** `render.py`, `validate.py`, renderer/validator tests

**Goal:** Generate all specified files only from manifests and reject inconsistent
runs.

**Deliverables:**

- `chapters.md`, `key-points.md`, transcript renderers, and `segments.json`;
- JSON schema validation;
- interval/order/coverage/path/frame checks;
- multilingual Markdown escaping and relative links;
- validator report and exit-code mapping.

**Tests:**

- golden outputs for English and Chinese fixtures;
- broken frame link, duplicate ID, overlap, out-of-range time, and invalid schema
  fail clearly;
- render is deterministic and idempotent.

**Acceptance:** A fully mocked run renders exactly the documented tree and
`vseg validate` reports zero errors.

### T13A — Representative-frame annotation and indexes

**Dependencies:** T01, T11, T12, T13  
**Can run in parallel:** yes, after the frame and segment contracts stabilize  
**Owned files:** `frame_annotations.py`, `frame-index.schema.json`, annotation tests

**Goal:** Make every selected representative frame immediately traceable to its source
timestamp and semantic scene without persisting all decoded frames.

**Deliverables:**

- additive timestamp/scene overlay under `frames/annotated/`;
- Unicode-preserving, path-safe, byte-bounded scene filenames;
- authoritative JSON index plus equivalent CSV and Markdown tables;
- approximate source-frame number derived from average FPS when available;
- configurable font, overlay fields, JPEG quality, and filename behavior;
- `vseg annotate-frames RUN_DIR` retrofit command;
- automatic regeneration after human title/frame overrides;
- stale annotated-file cleanup while preserving canonical frames; and
- backward-compatible validation for pre-0.2 runs.

**Tests:**

- timestamp formatting and estimated frame number;
- Chinese/English scene names and unsafe-character normalization;
- long multibyte titles remain below filesystem filename limits;
- JSON, CSV, and Markdown contain matching frame records;
- Markdown relative image links resolve;
- rerender removes a stale scene filename after title review;
- retrofit CLI operates without invoking analysis providers; and
- full pipeline validation requires annotation artifacts for new 0.2 runs.

**Acceptance:** Every representative frame in a new run has one readable annotated
copy and one consistent index row; a 0.1 run can be retrofitted without ASR,
segmentation, or source-media modification.

### T14 — CLI and pipeline orchestration

**Dependencies:** T02–T13 and T13A  
**Can run in parallel:** no; final integration owner  
**Owned files:** `cli.py`, `pipeline.py`, orchestration tests

**Goal:** Connect stages into `analyze`, `resume`, `validate`, and `render`.

**Deliverables:**

- CLI options and exit codes from `SPEC.md`;
- dependency-injected stage registry;
- effective-config resolution;
- run matching by source/config hash;
- checkpoint reuse and partial/review reporting;
- graceful interrupt handling;
- clear progress without transcript leakage in logs.

**Tests:**

- mocked successful full run;
- missing provider and corrupt input exit codes;
- interrupt/resume;
- `--force-new-run` behavior;
- local-only default rejects configured network provider without explicit opt-in.

**Acceptance:** A mocked CLI run survives interruption and produces one validated
run directory on resume.

### T15 — Fixture and evaluation harness

**Dependencies:** T00, T01  
**Can run in parallel:** yes; start early  
**Owned files:** `evaluation/*`, fixture manifests, evaluation tests

**Goal:** Make quality measurable rather than subjective.

**Deliverables:**

- reference-annotation schema;
- topic precision/recall/F1 matching;
- boundary median/P90 error;
- title/proper-name scoring hooks;
- representative-frame acceptance calculation;
- runtime/memory result ingestion;
- machine-readable and Markdown evaluation reports.

**Tests:**

- hand-calculated toy examples;
- unmatched/duplicate prediction behavior;
- tolerance-boundary edge cases;
- deterministic reports.

**Acceptance:** Toy fixtures reproduce expected metrics exactly.

### T16 — End-to-end integration and POC migration test

**Dependencies:** T14, T15  
**Can run in parallel:** no  
**Owned files:** end-to-end tests, integration configs, migration notes

**Goal:** Demonstrate that the generic pipeline handles the original POC video
without production hard-coding and evaluate two additional styles.

**Deliverables:**

- opt-in local integration profile using real providers;
- original POC video evaluation adapter outside production code;
- one implicit-transition narrated evaluation;
- one lightly narrated/music-heavy evaluation;
- performance and quality report;
- issue list for acceptance-gate misses.

**Tests:**

- production-source scan for prohibited filename, timestamps, phrases, and manual
  correction list;
- source hashes unchanged;
- outputs validate with no broken links;
- interrupted real-provider run resumes.

**Acceptance:** All version 1 gates are measured. Failures are reported honestly;
this task does not lower thresholds to declare success.

### T17 — Human review overrides

**Dependencies:** T13, T14  
**Can run in parallel:** after rendered contracts stabilize  
**Owned files:** review/override module and tests

**Goal:** Allow a reviewer to adjust boundaries, titles, and representative frames
without editing raw provider artifacts.

**Deliverables:**

- separate `overrides.json` schema;
- commands to set title, start/end, chosen frame, and verification status;
- validation against neighboring segments/source duration;
- rerender using raw results plus overrides;
- audit fields with timestamp and optional reviewer label.

**Tests:**

- valid override changes rendered output only;
- raw transcript/evidence remains byte-identical;
- invalid overlap/out-of-range frame is rejected;
- override persists after rerender/resume.

**Acceptance:** A reviewer can correct one title, boundary, and frame, rerender,
and retain full provenance.

### T18 — Packaging, operations, and user documentation

**Dependencies:** T16, T17  
**Can run in parallel:** final task  
**Owned files:** `README.md`, install/run guides, model/privacy docs, release config

**Goal:** Produce a reproducible handoff suitable for a user or operations agent.

**Deliverables:**

- CPU installation and optional accelerator instructions;
- provider/model download and cache documentation;
- privacy/network disclosure;
- configuration reference;
- examples for analyze/resume/validate/review;
- troubleshooting for codec, model, OCR, VAD, memory, and corrupt input failures;
- release/versioning process and clean-install test.

**Tests:**

- documentation commands run in a clean environment where practical;
- package build/install smoke test;
- no credentials, source videos, run outputs, or model weights in package.

**Acceptance:** A new operator can install, analyze a small fixture, interrupt,
resume, validate, and review it using only documented commands.

## 9. Suggested Assignment Waves

### Wave 1 — Foundation

- Agent A: T00
- Agent B after T00: T01
- Agent C after T00/T01: begin T15

### Wave 2 — Parallel evidence providers

- Agent A: T02
- Agent B: T03
- Agent C: T04
- Agent D: T06

### Wave 3 — Recovery and semantic preparation

- Agent A: T05
- Agent B: T07
- Agent C: T08 then T09
- Agent D: continue T15 fixtures

### Wave 4 — Fusion and outputs

- Integration-experienced agent: T10
- Agent B: T11
- Agent C: T12
- Agent D: T13

### Wave 5 — Product integration

- Integration owner: T14
- Evaluation owner: T16
- Agent B: T17
- Documentation/release owner: T18

Assignments are suggestions, not authorization for agents to edit overlapping
files concurrently.

## 10. Reviewer Checklists

### Contract review

- Does the change conform to `SPEC.md` schemas and states?
- Is provider-specific behavior behind an interface?
- Is uncertainty represented rather than hidden?
- Are paths relative and contained?
- Are raw artifacts immutable?

### Algorithm review

- Does the implementation confuse shots with semantic segments?
- Does it use the full transcript/global outline?
- Are fixed chunks only processing units, not final chapters?
- Are evidence weights configurable/versioned?
- Can low-confidence decisions become `needs_review`?

### Test review

- Do unit tests run offline?
- Are implicit transitions and no-speech cases covered?
- Is interruption/resume tested?
- Are multilingual and variable-frame-rate cases covered?
- Are claimed quality numbers generated by the evaluation harness?

### Security/privacy review

- Is network use opt-in and disclosed?
- Can paths escape the run directory?
- Are secrets/transcripts leaked into logs?
- Are model versions pinned?
- Is source media byte-identical after the test?

## 11. Agent Handoff Template

```markdown
# Handoff: Txx — Task name

## Outcome
One paragraph describing the implemented behavior.

## Files changed
- path: purpose

## Public contracts
- Added/changed/unchanged

## Verification
- command
- result

## Assumptions
- assumption

## Known limitations
- limitation

## Follow-up for dependent tasks
- dependency note

## Safety
- Source media modified: no
- Network/model downloads during tests: no
```
