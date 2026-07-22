# ViSS Deliverables Archive Manifest

Archive created on 2026-07-16.

## Included

- `video-semantic-segmenter/`: ViSS source, tests, schemas, documentation, lockfile,
  and built wheel/source distribution.
- `video-semantic-segmenter-spec/`: implementation specification and engineering tasks.
- `神奇美景在中国-宋春玲/poc-output/`: initial proof-of-concept results.
- `神奇美景在中国-宋春玲/generic-vseg-output/`: final reusable ViSS results.
- `中国美景大全-王宇梅/viss-output/`: final reusable ViSS results.
- `DESIGN-v2.md`: YouTube/Telegram wishlist design.
- `hello.js`: requested small Node.js example.
- This manifest.

## Excluded original user sources

- `yt-queue-poc.zip`
- `神奇美景在中国-宋春玲.zip`
- `神奇美景在中国-宋春玲/神奇美景在中国-宋春玲.mp4`
- `神奇美景在中国-宋春玲/神奇美景在中国-宋春玲.mp3`
- `神奇美景在中国-宋春玲/video_frames/`
- `神奇美景在中国-宋春玲/video_frames_dense-5sec/`
- `中国美景大全-王宇梅/中国美景大全-王宇梅.mp4`

## Excluded generated local environments and caches

- `video-semantic-segmenter/.venv/`
- `.pytest_cache/`, `.ruff_cache/`, and all `__pycache__/` directories

The destination system should recreate the Python environment using `uv.lock` and the
deployment instructions in `video-semantic-segmenter/IMPLEMENTATION-REPORT.md`.
