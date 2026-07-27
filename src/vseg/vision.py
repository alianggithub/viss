from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import VisionRecognitionConfig
from .models import EvidenceEvent, SemanticSegment
from .render import format_timestamp


@dataclass(slots=True)
class VisionResult:
    description: str
    relevance_score: float | None
    model: str
    raw_response: str


class OpenAICompatibleVisionRecognizer:
    """Small dependency-free client for a local vLLM/SGLang OpenAI-compatible server."""

    def __init__(self, config: VisionRecognitionConfig):
        self.config = config
        self.base_url = config.endpoint.rstrip("/")

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = Request(f"{self.base_url}{path}", data=data, headers=headers)
        with urlopen(request, timeout=self.config.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    def available_models(self) -> set[str]:
        payload = self._request("/models")
        return {str(item.get("id")) for item in payload.get("data", []) if item.get("id")}

    def is_available(self) -> bool:
        try:
            models = self.available_models()
            return not models or self.config.model in models
        except (OSError, ValueError, KeyError, URLError, TimeoutError):
            return False

    def recognize(self, image_path: Path, prompt: str) -> VisionResult:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        suffix = image_path.suffix.lower()
        media_type = "image/png" if suffix == ".png" else "image/jpeg"
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
        }
        response = self._request("/chat/completions", payload)
        content = response["choices"][0]["message"]["content"]
        if isinstance(content, list):
            raw = "\n".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            ).strip()
        else:
            raw = str(content).strip()
        parsed = _parse_response(raw)
        return VisionResult(
            description=parsed["description"],
            relevance_score=parsed.get("relevance_score"),
            model=self.config.model,
            raw_response=raw,
        )


def _parse_response(raw: str) -> dict[str, Any]:
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        value = json.loads(candidate)
        description = str(value.get("description", "")).strip()
        relevance = value.get("relevance_score")
        if relevance is not None:
            relevance = max(0.0, min(1.0, float(relevance)))
        if description:
            return {"description": description, "relevance_score": relevance}
    except (ValueError, TypeError, AttributeError):
        pass
    return {"description": raw.strip(), "relevance_score": None}


def recognize_segment_frames(
    run_dir: Path,
    segments: list[SemanticSegment],
    config: VisionRecognitionConfig,
    recognizer: OpenAICompatibleVisionRecognizer | None = None,
) -> tuple[list[EvidenceEvent], list[str]]:
    """Describe representative frames when a configured local vision server is available."""
    if config.mode == "off":
        return [], []
    recognizer = recognizer or OpenAICompatibleVisionRecognizer(config)
    if not recognizer.is_available():
        message = (
            f"vision model unavailable at {config.endpoint}; expected {config.model}. "
            "Start the configured local server or use vision.mode=off."
        )
        if config.mode == "on":
            raise RuntimeError(message)
        return [], [message]

    events: list[EvidenceEvent] = []
    warnings: list[str] = []
    for segment in segments:
        frame = segment.representative_frame
        if frame is None:
            continue
        image_path = run_dir / frame.path
        prompt = (
            "Describe the main visible subject, location, or activity in this video frame in "
            "one concise factual sentence. Do not identify a specific place unless visible "
            f"evidence supports it. The transcript topic is: {segment.title!r}. Return JSON "
            'with keys "description" and "relevance_score" (0 to 1 for relevance to the topic).'
        )
        try:
            result = recognizer.recognize(image_path, prompt)
        except Exception as exc:
            message = f"vision recognition failed for {segment.id}: {type(exc).__name__}: {exc}"
            if config.mode == "on":
                raise RuntimeError(message) from exc
            warnings.append(message)
            continue
        if frame is not None and result.relevance_score is not None:
            frame.relevance_score = result.relevance_score
        events.append(
            EvidenceEvent(
                id=f"vision-description-{segment.id}",
                timestamp_s=frame.timestamp_s,
                end_s=None,
                source="vision",
                kind="representative_frame_description",
                score=result.relevance_score,
                provider=f"openai-compatible:{result.model}",
                payload={
                    "segment_id": segment.id,
                    "segment_title": segment.title,
                    "frame_path": frame.path,
                    "description": result.description,
                    "raw_response": result.raw_response,
                },
            )
        )
    return events, warnings


def render_visual_descriptions(run_dir: Path, events: list[EvidenceEvent]) -> None:
    lines = ["# Visual descriptions", ""]
    if not events:
        lines.append("No vision-model descriptions were produced.")
    for event in events:
        title = str(event.payload.get("segment_title") or event.payload.get("segment_id"))
        description = str(event.payload.get("description") or "")
        lines.extend(
            [
                f"## {format_timestamp(event.timestamp_s).split('.')[0]} — {title}",
                "",
                description,
                "",
            ]
        )
    (run_dir / "visual-descriptions.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
