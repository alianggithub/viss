from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .io import atomic_write_json, read_json


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class CheckpointStore:
    run_dir: Path

    @property
    def directory(self) -> Path:
        return self.run_dir / "checkpoints"

    def path_for(self, stage: str, item_id: str | None = None) -> Path:
        safe_stage = stage.replace("/", "_")
        name = safe_stage if item_id is None else f"{safe_stage}--{item_id.replace('/', '_')}"
        return self.directory / f"{name}.json"

    def load_valid(
        self,
        stage: str,
        input_hash: str,
        config_hash: str,
        provider_version: str,
        item_id: str | None = None,
    ) -> dict[str, Any] | None:
        path = self.path_for(stage, item_id)
        if not path.exists():
            return None
        try:
            value = read_json(path)
        except (OSError, ValueError):
            return None
        expected = (input_hash, config_hash, provider_version, "complete")
        actual = (
            value.get("input_hash"),
            value.get("config_hash"),
            value.get("provider_version"),
            value.get("status"),
        )
        return value if actual == expected else None

    def save(
        self,
        stage: str,
        status: str,
        input_hash: str,
        config_hash: str,
        provider_version: str,
        outputs: dict[str, Any],
        item_id: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        atomic_write_json(
            self.path_for(stage, item_id),
            {
                "stage": stage,
                "item_id": item_id,
                "status": status,
                "input_hash": input_hash,
                "config_hash": config_hash,
                "provider_version": provider_version,
                "updated_at": utc_now(),
                "outputs": outputs,
                "error": error,
            },
        )
