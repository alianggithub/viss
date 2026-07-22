from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from .config import SemanticConfig
from .evidence import finite_score
from .models import (
    BoundaryCandidate,
    EvidenceEvent,
    KeyPoint,
    SemanticSegment,
    Transcript,
    TranscriptWord,
)

_TERMINAL = re.compile(r"[。.!！？?；;]$")
_CLAUSE = re.compile(r"[，,：:]$")
_HAN = re.compile(r"[\u3400-\u9fff]")
_WORD = re.compile(r"[\w]+", re.UNICODE)


@dataclass(slots=True)
class TextUnit:
    id: str
    start_s: float
    end_s: float
    text: str
    transcript_refs: list[str]
    tokens: tuple[str, ...]


def _lexical_tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    han = "".join(_HAN.findall(normalized))
    tokens: list[str] = []
    if han:
        tokens.extend(han[index : index + 2] for index in range(max(1, len(han) - 1)))
    tokens.extend(item for item in _WORD.findall(normalized) if not _HAN.search(item))
    return tuple(tokens)


def transcript_units(transcript: Transcript, pause_s: float) -> list[TextUnit]:
    """Split word-timestamp ASR into clauses without assuming a language."""
    words: list[tuple[TranscriptWord, str]] = []
    for segment in transcript.segments:
        if segment.words:
            words.extend((word, segment.id) for word in segment.words)
        elif segment.text.strip():
            pseudo = TranscriptWord(
                id=f"{segment.id}-text",
                start_s=segment.start_s,
                end_s=segment.end_s,
                text=segment.text.strip(),
            )
            words.append((pseudo, segment.id))
    words.sort(key=lambda item: (item[0].start_s, item[0].end_s))
    units: list[TextUnit] = []
    current: list[tuple[TranscriptWord, str]] = []

    def flush() -> None:
        if not current:
            return
        text = "".join(item[0].text for item in current).strip()
        if text:
            refs = list(dict.fromkeys(item[1] for item in current))
            units.append(
                TextUnit(
                    id=f"unit-{len(units)}",
                    start_s=current[0][0].start_s,
                    end_s=current[-1][0].end_s,
                    text=text,
                    transcript_refs=refs,
                    tokens=_lexical_tokens(text),
                )
            )
        current.clear()

    for word, segment_ref in words:
        if current and (
            segment_ref != current[-1][1] or word.start_s - current[-1][0].end_s >= pause_s
        ):
            flush()
        current.append((word, segment_ref))
        if _TERMINAL.search(word.text.strip()) or _CLAUSE.search(word.text.strip()):
            flush()
    flush()
    return units


def _prefix_normalized(text: str) -> str:
    raw = unicodedata.normalize("NFKC", text).lower()
    if _HAN.search(raw):
        return "".join(character for character in raw if character.isalnum())
    return " ".join(_WORD.findall(raw))


def _prefix_keys(text: str) -> Iterable[str]:
    normalized = _prefix_normalized(text)
    if not normalized:
        return ()
    if _HAN.search(normalized):
        return tuple(normalized[:size] for size in range(2, min(7, len(normalized) + 1)))
    words = _WORD.findall(normalized)
    return tuple(" ".join(words[:size]) for size in range(1, min(4, len(words) + 1)))


def discover_repeated_prefixes(units: list[TextUnit], minimum_count: int = 3) -> set[str]:
    counts = Counter(prefix for unit in units for prefix in _prefix_keys(unit.text))
    if not counts:
        return set()
    adaptive_minimum = max(minimum_count, math.ceil(max(counts.values()) * 0.08))
    eligible = {prefix for prefix, count in counts.items() if count >= adaptive_minimum}
    # Use a longer form only when it represents a substantial share of the shorter form.
    # This keeps a 67-use opener from being replaced by an accidental 3-use prefix.
    return {
        prefix
        for prefix in eligible
        if not any(
            other.startswith(prefix) and other != prefix and counts[other] >= 0.4 * counts[prefix]
            for other in eligible
        )
    }


def _jaccard_distance(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return 1.0 - len(a & b) / len(a | b)


def _cohesion_distances(units: list[TextUnit], window: int = 3) -> list[float]:
    distances = [1.0]
    for index in range(1, len(units)):
        left = tuple(
            token for unit in units[max(0, index - window) : index] for token in unit.tokens
        )
        right = tuple(token for unit in units[index : index + window] for token in unit.tokens)
        distances.append(_jaccard_distance(left, right))
    return distances


def semantic_candidates(
    transcript: Transcript, config: SemanticConfig
) -> tuple[list[BoundaryCandidate], list[TextUnit]]:
    units = transcript_units(transcript, config.pause_threshold_s)
    prefixes = discover_repeated_prefixes(units)
    lexical_distances = _cohesion_distances(units)
    repeated_times = [
        unit.start_s
        for unit in units
        if any(_prefix_normalized(unit.text).startswith(prefix) for prefix in prefixes)
    ]
    candidates: list[BoundaryCandidate] = []
    last_lexical_time = -float("inf")
    for index, unit in enumerate(units):
        normalized_unit = _prefix_normalized(unit.text)
        matched = sorted(
            (prefix for prefix in prefixes if normalized_unit.startswith(prefix)),
            key=len,
            reverse=True,
        )
        pause = unit.start_s - units[index - 1].end_s if index else unit.start_s
        lexical = lexical_distances[index]
        repeated = bool(matched)
        neighborhood = lexical_distances[max(0, index - 2) : index + 3]
        local_peak = lexical >= max(neighborhood, default=lexical)
        far_from_repeated = (
            not repeated_times
            or min(abs(unit.start_s - timestamp) for timestamp in repeated_times) >= 8.0
        )
        lexical_boundary = (
            local_peak
            and far_from_repeated
            and lexical >= config.lexical_change_threshold
            and unit.start_s - last_lexical_time >= 8.0
        )
        raw = max(
            0.88 if repeated else 0.0,
            0.72 if pause >= config.pause_threshold_s else 0.0,
            0.56 * lexical if lexical_boundary else 0.0,
        )
        if index == 0:
            raw = 1.0
        if raw < config.min_candidate_score:
            continue
        if lexical_boundary and not repeated and pause < config.pause_threshold_s:
            last_lexical_time = unit.start_s
        kind = (
            "repeated_discourse_opening"
            if repeated
            else ("speech_pause" if pause >= config.pause_threshold_s else "lexical_change")
        )
        candidates.append(
            BoundaryCandidate(
                id=f"semantic-{len(candidates)}",
                timestamp_s=unit.start_s,
                source="transcript",
                kind=kind,
                raw_score=raw,
                normalized_score=raw,
                provider="vseg-semantic-heuristic-v1",
                evidence_refs=[unit.id],
                payload={
                    "text": unit.text,
                    "prefix": matched[0] if matched else None,
                    "pause_s": round(max(0.0, pause), 3),
                    "lexical_distance": round(lexical, 3),
                },
            )
        )
    return candidates, units


def event_candidates(events: list[EvidenceEvent]) -> list[BoundaryCandidate]:
    weights = {"ocr": 0.64, "chapter": 0.95, "visual": 0.26, "audio": 0.42}
    result = []
    for event in events:
        score = finite_score(event.score, 0.5) * weights.get(event.source, 0.35)
        result.append(
            BoundaryCandidate(
                id=f"candidate-{event.id}",
                timestamp_s=event.timestamp_s,
                source=event.source,
                kind=event.kind,
                raw_score=score,
                normalized_score=score,
                provider=event.provider,
                evidence_refs=[event.id],
                payload=event.payload.copy(),
            )
        )
    return result


def fuse_candidates(
    candidates: list[BoundaryCandidate], config: SemanticConfig, duration_s: float
) -> list[BoundaryCandidate]:
    """Cluster multimodal evidence; isolated visual edits cannot create chapters."""
    ordered = sorted(
        (item for item in candidates if 0 <= item.timestamp_s < duration_s),
        key=lambda item: item.timestamp_s,
    )
    clusters: list[list[BoundaryCandidate]] = []
    for item in ordered:
        if (
            not clusters
            or item.timestamp_s - clusters[-1][-1].timestamp_s > config.candidate_merge_s
        ):
            clusters.append([item])
        else:
            clusters[-1].append(item)
    fused: list[BoundaryCandidate] = []
    for cluster_index, cluster in enumerate(clusters):
        semantic = [item for item in cluster if item.source in {"transcript", "chapter"}]
        if not semantic:
            continue
        weights = [max(0.05, item.normalized_score) for item in cluster]
        timestamp = sum(
            item.timestamp_s * weight for item, weight in zip(cluster, weights, strict=True)
        ) / sum(weights)
        confidence = 1.0 - math.prod(1.0 - min(0.95, item.normalized_score) for item in cluster)
        anchor = max(
            cluster,
            key=lambda item: (item.source in {"transcript", "chapter"}, item.normalized_score),
        )
        fused.append(
            BoundaryCandidate(
                id=f"boundary-{cluster_index}",
                timestamp_s=timestamp,
                source="fusion",
                kind=anchor.kind,
                raw_score=confidence,
                normalized_score=min(1.0, confidence),
                provider="vseg-fusion-v1",
                evidence_refs=[ref for item in cluster for ref in item.evidence_refs],
                payload={"sources": sorted({item.source for item in cluster}), **anchor.payload},
                cluster_id=f"cluster-{cluster_index}",
            )
        )
    if not fused or fused[0].timestamp_s > 0.25:
        fused.insert(
            0,
            BoundaryCandidate(
                "boundary-start", 0.0, "system", "media_start", 1.0, 1.0, "vseg-fusion-v1"
            ),
        )
    else:
        fused[0].timestamp_s = 0.0
    collapsed: list[BoundaryCandidate] = []
    for item in fused:
        if collapsed and item.timestamp_s - collapsed[-1].timestamp_s < 0.5:
            if (
                item.normalized_score > collapsed[-1].normalized_score
                and collapsed[-1].timestamp_s > 0
            ):
                collapsed[-1] = item
            continue
        collapsed.append(item)
    return collapsed


def _clean_title(text: str, limit: int = 56) -> str:
    value = re.sub(r"\s+", " ", text).strip(" ,，。.!！?？:：;；")
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def build_segments(
    boundaries: list[BoundaryCandidate],
    units: list[TextUnit],
    ocr_events: list[EvidenceEvent],
    duration_s: float,
    language: str,
) -> list[SemanticSegment]:
    segments: list[SemanticSegment] = []
    for index, boundary in enumerate(boundaries):
        start = max(0.0, boundary.timestamp_s)
        end = boundaries[index + 1].timestamp_s if index + 1 < len(boundaries) else duration_s
        if end - start < 0.25:
            continue
        inside = [unit for unit in units if unit.end_s > start and unit.start_s < end]
        nearby_ocr = [
            event
            for event in ocr_events
            if start - 0.5 <= event.timestamp_s < min(end, start + 4.0)
            and event.payload.get("text")
        ]
        title_options = [
            _clean_title(str(event.payload["text"]))
            for event in sorted(nearby_ocr, key=lambda e: finite_score(e.score), reverse=True)
        ]
        title_options.extend(_clean_title(unit.text) for unit in inside[:2])
        title_options = list(dict.fromkeys(value for value in title_options if value))
        title = title_options[0] if title_options else f"Segment {len(segments) + 1}"
        key_points = [
            KeyPoint(text=_clean_title(unit.text, 180), evidence_refs=[unit.id], confidence=0.65)
            for unit in inside[:5]
            if _clean_title(unit.text, 180)
        ]
        refs = list(dict.fromkeys(ref for unit in inside for ref in unit.transcript_refs))
        segments.append(
            SemanticSegment(
                id=f"segment-{len(segments) + 1:04d}",
                start_s=start,
                end_s=end,
                type="topic",
                title=title,
                title_language=language,
                title_confidence=0.78 if nearby_ocr else (0.62 if inside else 0.2),
                title_alternatives=title_options[1:4],
                key_points=key_points,
                boundary_confidence=boundary.normalized_score,
                boundary_algorithm_version="vseg-fusion-v1",
                boundary_evidence_refs=boundary.evidence_refs,
                boundary_needs_review=boundary.normalized_score < 0.65,
                transcript_segment_refs=refs,
            )
        )
    return segments
