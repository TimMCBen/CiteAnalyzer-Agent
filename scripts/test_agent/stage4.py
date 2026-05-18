"""Validate Stage 4 author profile enrichment and scholar labels."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.author_intel.service import analyze_author_intel
from packages.citation_sources.models import CitingPaper
from scripts.test_agent.stage_logging import StageLogger


class FakeOpenAlexClient:
    """Fake OpenAlex client returning author profile fixtures."""
    def lookup_author(self, name: str):
        """Return an OpenAlex-style author profile for known names."""
        mapping = {
            "Alice Smith": {
                "author_id": "https://openalex.org/A1",
                "name": "Alice Smith",
                "source_ids": {"openalex": "https://openalex.org/A1"},
                "affiliations": ["Tsinghua University"],
                "fields": ["Natural Language Processing"],
                "h_index": 42,
                "citation_count": 800,
                "works_count": 50,
                "evidence_sources": ["openalex"],
            },
            "Bob Lee": {
                "author_id": "https://openalex.org/A2",
                "name": "Bob Lee",
                "source_ids": {"openalex": "https://openalex.org/A2"},
                "affiliations": ["Peking University"],
                "fields": ["Machine Learning"],
                "h_index": 35,
                "citation_count": 400,
                "works_count": 30,
                "evidence_sources": ["openalex"],
            },
            "Carol Ng": {
                "author_id": "https://openalex.org/A3",
                "name": "Carol Ng",
                "source_ids": {"openalex": "https://openalex.org/A3"},
                "affiliations": ["NUS"],
                "fields": ["Information Retrieval"],
                "h_index": None,
                "citation_count": 120,
                "works_count": 12,
                "evidence_sources": ["openalex"],
            },
        }
        return mapping.get(name)


class FakeDBLPClient:
    """Fake DBLP client returning fallback author profile fixtures."""
    def lookup_author(self, name: str):
        """Return a DBLP-style fallback profile for known names."""
        mapping = {
            "Carol Ng": {
                "author_id": "https://dblp.org/pid/03/9999",
                "name": "Carol Ng",
                "source_ids": {"dblp": "https://dblp.org/pid/03/9999"},
                "affiliations": [],
                "fields": [],
                "h_index": None,
                "citation_count": None,
                "works_count": None,
                "evidence_sources": ["dblp"],
            }
        }
        return mapping.get(name)


def build_citing_papers() -> list[CitingPaper]:
    """Build citing-paper fixtures with repeated and weak authors."""
    return [
        CitingPaper(
            canonical_id="paper-1",
            title="Transformer Citation Study",
            doi="10.1000/a",
            year=2021,
            authors=["Alice Smith", "Bob Lee"],
        ),
        CitingPaper(
            canonical_id="paper-2",
            title="Follow-up Analysis",
            doi="10.1000/b",
            year=2022,
            authors=["Alice Smith", "Carol Ng"],
        ),
        CitingPaper(
            canonical_id="paper-3",
            title="Weak Evidence Case",
            doi="10.1000/c",
            year=2023,
            authors=["Zed Unknown"],
        ),
    ]


def assert_stage4_labels():
    result = analyze_author_intel(
        citing_papers=build_citing_papers(),
        openalex_client=FakeOpenAlexClient(),
        dblp_client=FakeDBLPClient(),
    )

    assert len(result.author_profiles) == 4, len(result.author_profiles)
    labels = {label.author_id: label for label in result.scholar_labels}
    profiles = {profile.name: profile for profile in result.author_profiles}

    alice_profile = profiles["Alice Smith"]
    alice_label = labels[alice_profile.author_id]
    assert alice_label.label == "heavyweight_candidate", alice_label

    bob_profile = profiles["Bob Lee"]
    bob_label = labels[bob_profile.author_id]
    assert bob_label.label == "high_impact_candidate", bob_label

    carol_profile = profiles["Carol Ng"]
    carol_label = labels[carol_profile.author_id]
    assert carol_label.label == "weak_signal_candidate", carol_label
    assert carol_label.confidence_note == "evidence_insufficient_missing_h_index", carol_label
    assert set(carol_profile.evidence_sources) == {"dblp", "openalex"}, carol_profile

    zed_profile = profiles["Zed Unknown"]
    zed_label = labels[zed_profile.author_id]
    assert zed_label.label == "weak_signal_candidate", zed_label
    assert not zed_profile.source_ids, zed_profile

    assert result.author_summary.total_authors == 4
    assert result.author_summary.heavyweight_candidates == 1
    assert result.author_summary.high_impact_candidates == 1
    assert result.author_summary.weak_signal_candidates == 2
    return result


def main() -> None:
    """Run Stage 4 author-intelligence assertions."""
    logger = StageLogger("stage4")
    logger.start()
    result = assert_stage4_labels()
    logger.pass_case(
        "author_intel_validation",
        detail=(
            f"citing_papers={len(build_citing_papers())} authors={len(result.author_profiles)} "
            f"heavyweight={result.author_summary.heavyweight_candidates} "
            f"high_impact={result.author_summary.high_impact_candidates} "
            f"weak_signal={result.author_summary.weak_signal_candidates} missing_h_index_covered=True"
        ),
    )
    logger.done("stage4 validation passed")


if __name__ == "__main__":
    main()
