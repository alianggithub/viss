import numpy as np

from vseg.frames import frame_quality


def test_black_frame_scores_below_detailed_frame() -> None:
    black = np.zeros((100, 100, 3), dtype=np.uint8)
    detailed = np.indices((100, 100)).sum(axis=0) % 2 * 255
    detailed_bgr = np.repeat(detailed[:, :, None], 3, axis=2).astype(np.uint8)
    assert frame_quality(black)[0] < frame_quality(detailed_bgr)[0]
