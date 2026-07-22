import json
from pathlib import Path

from vseg.evaluate import evaluate_run


def test_evaluation_metrics_and_frame_acceptance(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "segments.json").write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "id": "s1",
                        "start_s": 10.5,
                        "title": "Alpha",
                        "representative_frame": {"timestamp_s": 12.0},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "title": "Alpha",
                        "start_s": 10.0,
                        "boundary_tolerance_s": 2.0,
                        "acceptable_frame_ranges": [[11.0, 13.0]],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_run(run, reference)
    assert result["topic_f1"] == 1.0
    assert result["median_boundary_error_s"] == 0.5
    assert result["representative_frame_acceptance"] == 1.0
