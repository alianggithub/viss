from pathlib import Path

import pytest

from vseg.io import contained_path


def test_contained_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        contained_path(tmp_path, "../outside.jpg")


def test_contained_path_accepts_child(tmp_path: Path) -> None:
    assert contained_path(tmp_path, "frames/a.jpg") == tmp_path / "frames/a.jpg"
