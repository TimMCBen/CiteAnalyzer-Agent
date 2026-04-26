from __future__ import annotations

from packages.sentiment.models import SentimentLabel


POSITIVE_CUES = (
    "we build on",
    "we extend",
    "following",
    "inspired by",
    "adopt",
    "adopts",
    "use their",
    "uses their",
    "based on",
    "leverages",
    "outperforms",
    "effective",
)

CRITICAL_CUES = (
    "however",
    "limited",
    "limitation",
    "fails to",
    "challenge",
    "problematic",
    "insufficient",
    "weakness",
    "unlike",
    "does not",
    "cannot",
    "shortcoming",
)


def classify_sentiment(context_text: str) -> tuple[SentimentLabel, str]:
    normalized = " ".join(context_text.lower().split())
    if len(normalized) < 24:
        return "unknown", "context_too_short"

    positive_hits = [cue for cue in POSITIVE_CUES if cue in normalized]
    critical_hits = [cue for cue in CRITICAL_CUES if cue in normalized]

    if positive_hits and not critical_hits:
        return "positive", f"rule_positive:{positive_hits[0]}"
    if critical_hits and not positive_hits:
        return "critical", f"rule_critical:{critical_hits[0]}"
    if critical_hits and positive_hits:
        return "neutral", "mixed_positive_and_critical_cues"
    return "neutral", "default_neutral_without_polarized_cues"
