from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config, validate_config
from .evaluate import evaluate_run
from .frame_annotations import render_frame_annotations
from .io import read_json
from .pipeline import analyze
from .review import record_override, render_reviewed
from .user_frames import dump_user_frames, load_timestamp_requests
from .validate import validate_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vseg", description="Local transcript-first video semantic segmentation"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze_parser = subparsers.add_parser("analyze", help="analyze a video")
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("--output", type=Path)
    analyze_parser.add_argument("--config", type=Path)
    analyze_parser.add_argument("--language")
    analyze_parser.add_argument("--model", "--asr-model", dest="model")
    analyze_parser.add_argument("--semantic-provider")
    analyze_parser.add_argument("--device", choices=("auto", "cpu", "cuda"))
    analyze_parser.add_argument("--ocr", choices=("auto", "on", "off"))
    analyze_parser.add_argument("--vision", choices=("auto", "on", "off"))
    analyze_parser.add_argument("--vision-endpoint")
    analyze_parser.add_argument("--vision-model")
    analyze_parser.add_argument("--allow-network-models", action="store_true")
    analyze_parser.add_argument("--resume", action="store_true")
    analyze_parser.add_argument("--force-new-run", action="store_true")
    resume_parser = subparsers.add_parser("resume", help="resume an existing run")
    resume_parser.add_argument("run_dir", type=Path)
    validate_parser = subparsers.add_parser("validate", help="validate a completed run")
    validate_parser.add_argument("run_dir", type=Path)
    render_parser = subparsers.add_parser("render", help="rerender from raw results and overrides")
    render_parser.add_argument("run_dir", type=Path)
    render_parser.add_argument("--format", choices=("markdown", "json", "srt", "vtt"))
    annotate_parser = subparsers.add_parser(
        "annotate-frames", help="regenerate timestamped, scene-named frame outputs"
    )
    annotate_parser.add_argument("run_dir", type=Path)
    dump_parser = subparsers.add_parser(
        "dump-frames", help="extract quality-tuned annotated frames near user timestamps"
    )
    dump_parser.add_argument("input", type=Path)
    dump_parser.add_argument(
        "--timestamp",
        action="append",
        default=[],
        metavar="TIME[|LABEL]",
        help="repeatable: seconds, MM:SS, or HH:MM:SS, optionally followed by |label",
    )
    dump_parser.add_argument("--timestamps-file", type=Path)
    dump_parser.add_argument("--output", type=Path)
    dump_parser.add_argument("--config", type=Path)
    dump_parser.add_argument("--window", type=float, help="fine-tune radius in seconds")
    dump_parser.add_argument("--sample-fps", type=float)
    dump_parser.add_argument("--no-fine-tune", action="store_true")
    dump_parser.add_argument(
        "--raw-and-annotated",
        action="store_true",
        help="compatibility mode: retain both raw frames and annotated copies",
    )
    review_parser = subparsers.add_parser("review", help="record a non-destructive human override")
    review_parser.add_argument("run_dir", type=Path)
    review_parser.add_argument("segment_id")
    review_parser.add_argument("--title")
    review_parser.add_argument("--start", type=float)
    review_parser.add_argument("--end", type=float)
    review_parser.add_argument("--frame-timestamp", type=float)
    review_parser.add_argument("--reviewer")
    review_parser.add_argument("--verified", action="store_true")
    evaluate_parser = subparsers.add_parser("evaluate", help="score a run against annotations")
    evaluate_parser.add_argument("run_dir", type=Path)
    evaluate_parser.add_argument("reference", type=Path)
    return parser


def _apply_overrides(config, args) -> None:
    if getattr(args, "language", None):
        config.transcription.language = args.language
    if getattr(args, "model", None):
        config.transcription.model = args.model
    if getattr(args, "device", None):
        config.runtime.device = args.device
    if getattr(args, "ocr", None):
        config.ocr.mode = args.ocr
    if getattr(args, "semantic_provider", None):
        config.semantic.provider = args.semantic_provider
    if getattr(args, "vision", None):
        config.vision_recognition.mode = args.vision
    if getattr(args, "vision_endpoint", None):
        config.vision_recognition.endpoint = args.vision_endpoint
    if getattr(args, "vision_model", None):
        config.vision_recognition.model = args.vision_model
    if getattr(args, "allow_network_models", False):
        config.privacy.allow_network_models = True
    validate_config(config)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_run(args.run_dir.resolve())
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("valid")
            return 0
        if args.command == "render":
            render_reviewed(args.run_dir.resolve())
            print(f"rendered: {args.run_dir.resolve()}")
            return 0
        if args.command == "annotate-frames":
            run_dir = args.run_dir.resolve()
            config = load_config(run_dir / "config.json")
            segments = read_json(run_dir / "segments.json")["segments"]
            rows = render_frame_annotations(run_dir, segments, config.frame_annotation)
            print(f"annotated frames: {len(rows)}")
            return 0
        if args.command == "dump-frames":
            config = load_config(args.config)
            if args.window is not None:
                config.user_frame_dump.search_window_s = args.window
            if args.sample_fps is not None:
                config.user_frame_dump.sample_fps = args.sample_fps
            if args.no_fine_tune:
                config.user_frame_dump.fine_tune = False
            if args.raw_and_annotated:
                config.user_frame_dump.annotated_only = False
            validate_config(config)
            source = args.input.expanduser().resolve()
            output = args.output or source.parent / f"{source.stem}-timestamp-frames"
            requests = load_timestamp_requests(args.timestamp, args.timestamps_file)
            rows = dump_user_frames(
                source,
                output.expanduser().resolve(),
                requests,
                config.user_frame_dump,
                config.frame_annotation,
            )
            print(f"dumped frames: {len(rows)} to {output.expanduser().resolve()}")
            return 0
        if args.command == "review":
            record_override(
                args.run_dir.resolve(),
                args.segment_id,
                title=args.title,
                start_s=args.start,
                end_s=args.end,
                frame_timestamp_s=args.frame_timestamp,
                reviewer=args.reviewer,
                verified=args.verified,
            )
            print(f"reviewed: {args.segment_id}")
            return 0
        if args.command == "evaluate":
            result = evaluate_run(args.run_dir.resolve(), args.reference.resolve())
            print(
                f"precision={result['topic_precision']:.3f} "
                f"recall={result['topic_recall']:.3f} f1={result['topic_f1']:.3f}"
            )
            return 0
        if args.command == "resume":
            run_dir = args.run_dir.resolve()
            source_data = read_json(run_dir / "source.json")
            config = load_config(run_dir / "config.json")
            result = analyze(Path(source_data["path"]), run_dir, config, resume=True)
        else:
            config = load_config(args.config)
            _apply_overrides(config, args)
            source = args.input.expanduser().resolve()
            output = args.output or source.parent / f"{source.stem}-viss-analysis"
            if args.force_new_run and output.exists() and any(output.iterdir()):
                from datetime import UTC, datetime

                suffix = datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")
                output = output / suffix
            result = analyze(source, output, config, resume=args.resume)
        print(f"complete: {result}")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
