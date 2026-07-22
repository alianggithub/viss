from vseg.config import SemanticConfig
from vseg.models import EvidenceEvent, Transcript, TranscriptSegment, TranscriptWord
from vseg.semantic import event_candidates, fuse_candidates, semantic_candidates


def _transcript() -> Transcript:
    phrases = ["Visit Alpha.", "Visit Beta.", "Visit Gamma."]
    segments = []
    for index, phrase in enumerate(phrases):
        start = index * 4.0
        word = TranscriptWord(f"w{index}", start, start + 1.0, phrase, 0.9)
        segments.append(TranscriptSegment(f"s{index}", start, start + 1.0, phrase, [word]))
    return Transcript("en", 0.99, 12.0, "fake", segments)


def test_repeated_opening_is_discovered_from_content() -> None:
    config = SemanticConfig(candidate_merge_s=0.5)
    candidates, _ = semantic_candidates(_transcript(), config)
    repeated = [item for item in candidates if item.kind == "repeated_discourse_opening"]
    assert len(repeated) == 3
    assert all(item.payload["prefix"] == "visit" for item in repeated)


def test_isolated_visual_cuts_do_not_create_segments() -> None:
    config = SemanticConfig(candidate_merge_s=0.5)
    semantic, _ = semantic_candidates(_transcript(), config)
    visual = [
        EvidenceEvent(f"v{i}", i + 0.25, None, "visual", "hard_visual_cut", 1.0, "fake")
        for i in range(11)
    ]
    fused = fuse_candidates(semantic + event_candidates(visual), config, 12.0)
    assert [round(item.timestamp_s) for item in fused] == [0, 4, 8]
