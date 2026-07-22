from pathlib import Path

import pytest

from vseg.config import Config, load_config


def test_default_config_hash_is_stable() -> None:
    assert Config().sha256() == Config().sha256()
    assert len(Config().sha256()) == 64


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("semantic:\n  mystery: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown configuration keys"):
        load_config(path)
