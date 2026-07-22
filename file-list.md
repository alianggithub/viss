# `/nobackup/chrgu/test` File and Archive Guide

This document explains every top-level file and folder currently associated with the
work. “Original input” means a file supplied by the user and intentionally excluded
from generated-results archives.

## Recommended deliverables

| Item | Type | Explanation |
| --- | --- | --- |
| `ViSS-video-processing-outputs-2026-07-16.zip` | Generated-output ZIP | Recommended archive for sharing the two videos' generated results. It includes the POC/final outputs, both manifests, this file list, and the technical specification. It excludes original media, ViSS source, `.venv`, and caches. |
| `video-semantic-segmenter/` | Application folder | Standalone ViSS source project: source code, tests, schemas, documentation, lockfile, and built packages. Its local `.venv` is machine-specific and should not be deployed. |
| `video-semantic-segmenter-spec/` | Documentation folder | Full ViSS architecture, interfaces, output contracts, acceptance criteria, and engineering task breakdown. Also included in the outputs ZIP. |

## Other ZIP and package archives

| Item | Origin | Explanation |
| --- | --- | --- |
| `ViSS-deliverables-2026-07-16.zip` | Generated | Earlier broad archive containing ViSS source/specification, generated video outputs, `DESIGN-v2.md`, and `hello.js`. It excludes original media and `.venv`. The outputs-only ZIP above is cleaner when only video results are wanted. |
| `yt-queue-poc.zip` | Original input | User-supplied YouTube/Telegram wishlist design and prototype. Preserved separately and excluded from generated-results archives. |
| `神奇美景在中国-宋春玲.zip` | Original input | User-supplied source package for the first video. Preserved separately and excluded from generated-results archives. |
| `video-semantic-segmenter/dist/video_semantic_segmenter-0.1.0-py3-none-any.whl` | Generated package | Installable ViSS Python wheel. Dependencies and the ASR model remain separate. |
| `video-semantic-segmenter/dist/video_semantic_segmenter-0.1.0.tar.gz` | Generated package | ViSS Python source distribution for building/installing the application. |

## Manifests and explanatory files

| Item | Explanation |
| --- | --- |
| `file-list.md` | This comprehensive file/archive orientation guide. |
| `ViSS-VIDEO-OUTPUTS-MANIFEST.md` | Exact contents and exclusions for the outputs-only ZIP. |
| `ViSS-ARCHIVE-MANIFEST.md` | Contents and exclusions for the earlier broad deliverables archive. |

## Video folders

| Item | Contents |
| --- | --- |
| `神奇美景在中国-宋春玲/` | First video's extracted original MP4, MP3, and supplied frame dumps; initial `poc-output/`; and final reusable `generic-vseg-output/`. Only the two output folders are copied into the outputs ZIP. |
| `中国美景大全-王宇梅/` | Second original MP4 and final `viss-output/`. Only `viss-output/` is copied into the outputs ZIP. |

Each final ViSS output contains chapters, key points, complete transcript formats,
representative frames, structured segments, multimodal evidence, checkpoints, logs,
configuration, reports, and validation metadata.

## Other generated work

| Item | Explanation |
| --- | --- |
| `DESIGN-v2.md` | Revised design for the YouTube/Telegram priority-comment workflow discussed before ViSS. |
| `hello.js` | Small requested Node.js “Hello, world” example. |

## Files intentionally not packaged with video outputs

- Original ZIP, MP4, and MP3 files.
- User-provided interval-frame folders.
- `video-semantic-segmenter/.venv/`.
- `.pytest_cache/`, `.ruff_cache/`, and `__pycache__/` directories.
- ASR model weights.

## Which item to use

- To inspect or share processing results, use
  `ViSS-video-processing-outputs-2026-07-16.zip`.
- To install or modify ViSS, use the `video-semantic-segmenter/` project folder and
  follow `IMPLEMENTATION-REPORT.md` inside it.
- To understand or extend the design, use `video-semantic-segmenter-spec/`.
- Keep original-input ZIPs and media as private source material outside deliverable
  archives.
