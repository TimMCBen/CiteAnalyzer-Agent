"""Rules helpers for author intelligence."""
from __future__ import annotations

from packages.shared.models import AuthorProfile, ScholarLabel


HIGH_IMPACT_H_INDEX = 30
HEAVYWEIGHT_MIN_FREQUENCY = 2


def build_scholar_label(profile: AuthorProfile, frequency: int) -> ScholarLabel:
    """Build scholar label for author intelligence."""
    evidence = [f"citation_frequency={frequency}"]
    trigger_rules: list[str] = []
    confidence_note: str | None = None

    if profile.h_index is not None:
        evidence.append(f"h_index={profile.h_index}")

    if profile.h_index is not None and profile.h_index >= HIGH_IMPACT_H_INDEX and frequency >= HEAVYWEIGHT_MIN_FREQUENCY:
        trigger_rules.extend(["h_index>=30", "frequency>=2"])
        return ScholarLabel(
            author_id=profile.author_id,
            label="heavyweight_candidate",
            evidence=evidence,
            confidence_note="matched_openalex_or_dblp_profile",
            trigger_rules=trigger_rules,
        )

    if profile.h_index is not None and profile.h_index >= HIGH_IMPACT_H_INDEX:
        trigger_rules.append("h_index>=30")
        return ScholarLabel(
            author_id=profile.author_id,
            label="high_impact_candidate",
            evidence=evidence,
            confidence_note="matched_openalex_or_dblp_profile",
            trigger_rules=trigger_rules,
        )

    trigger_rules.append("evidence_insufficient")
    if profile.h_index is None:
        confidence_note = "evidence_insufficient_missing_h_index"
    else:
        confidence_note = "evidence_insufficient_below_threshold"

    return ScholarLabel(
        author_id=profile.author_id,
        label="weak_signal_candidate",
        evidence=evidence,
        confidence_note=confidence_note,
        trigger_rules=trigger_rules,
    )
