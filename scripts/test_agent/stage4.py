"""Validate Stage 4 work-authorship author profile enrichment."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.author_intel.service import analyze_author_intel
from packages.citation_sources.models import CitingPaper
from packages.paper_identity.models import CandidateAuthor, CandidateWork
from scripts.test_agent.stage_logging import StageLogger


def work(
    title: str,
    *,
    doi: str | None,
    authors: list[CandidateAuthor],
    year: int = 2025,
    work_id: str = "https://openalex.org/W1",
) -> CandidateWork:
    """Build an OpenAlex work fixture with authorship ids."""
    return CandidateWork(
        source="openalex",
        work_id=work_id,
        title=title,
        doi=doi,
        year=year,
        authors=authors,
    )


def author(name: str, author_id: str | None, institutions: list[str] | None = None) -> CandidateAuthor:
    """Build a work-authorship author fixture."""
    return CandidateAuthor(
        name=name,
        author_id=author_id,
        institutions=institutions or [],
    )


class FakeOpenAlexWorkClient:
    """Fake OpenAlex work client that fails if name search is attempted."""
    def __init__(self) -> None:
        self.author_id_calls: list[str] = []

    def lookup_author(self, name: str):  # pragma: no cover - should never be called
        """Fail if the old name-search path is used."""
        raise AssertionError(f"name search must not be used: {name}")

    def lookup_work_by_doi(self, doi: str | None):
        """Return DOI-linked work fixtures."""
        if doi == "10.1000/high":
            return work(
                "Transformer Citation Study",
                doi=doi,
                authors=[
                    author("Alice Smith", "https://openalex.org/A1", ["Tsinghua University"]),
                    author("Bob Lee", "https://openalex.org/A2", ["Peking University"]),
                ],
                work_id="https://openalex.org/W-high",
            )
        if doi == "10.1000/variant":
            return work(
                "Follow-up Study for Transparent Models",
                doi=doi,
                authors=[
                    author("Alice Smith", "https://openalex.org/A1", ["Tsinghua University"]),
                    author("Carol Ng", "https://openalex.org/A3", ["National University of Singapore"]),
                ],
                work_id="https://openalex.org/W-variant",
            )
        if doi == "10.1000/no-author-id":
            return work(
                "No Author ID Case",
                doi=doi,
                authors=[author("No Id Author", None, ["Unknown Institute"])],
                work_id="https://openalex.org/W-no-author-id",
            )
        return None

    def search_work_by_title(self, title: str, *, per_page: int = 3):
        """Return no title-search candidates so DOI confidence controls fixtures."""
        _ = (title, per_page)
        return []

    def lookup_author_by_id(self, author_id: str | None):
        """Return author-id profiles for trusted work authorships."""
        if author_id:
            self.author_id_calls.append(author_id)
        mapping = {
            "https://openalex.org/A1": {
                "author_id": "https://openalex.org/A1",
                "name": "Alice Smith",
                "source_ids": {"openalex": "https://openalex.org/A1"},
                "affiliations": ["Tsinghua University"],
                "fields": ["Natural Language Processing"],
                "h_index": 42,
                "citation_count": 800,
                "works_count": 50,
                "evidence_sources": ["openalex_author_id"],
            },
            "https://openalex.org/A2": {
                "author_id": "https://openalex.org/A2",
                "name": "Bob Lee",
                "source_ids": {"openalex": "https://openalex.org/A2"},
                "affiliations": ["Peking University"],
                "fields": ["Machine Learning"],
                "h_index": 35,
                "citation_count": 400,
                "works_count": 30,
                "evidence_sources": ["openalex_author_id"],
            },
            "https://openalex.org/A3": {
                "author_id": "https://openalex.org/A3",
                "name": "Carol Ng",
                "source_ids": {"openalex": "https://openalex.org/A3"},
                "affiliations": ["National University of Singapore"],
                "fields": ["Information Retrieval"],
                "h_index": None,
                "citation_count": 120,
                "works_count": 12,
                "evidence_sources": ["openalex_author_id"],
            },
        }
        return mapping.get(str(author_id))


class FakeArxivClient:
    """Fake arXiv client returning no supplemental candidates."""
    def lookup_ids(self, arxiv_ids: list[str]):
        """Return no arXiv ID candidates."""
        _ = arxiv_ids
        return []

    def search_by_title(self, title: str, *, max_results: int = 3):
        """Return no arXiv title candidates."""
        _ = (title, max_results)
        return []


def build_citing_papers() -> list[CitingPaper]:
    """Build citing-paper fixtures for trusted and skipped author paths."""
    return [
        CitingPaper(
            canonical_id="paper-high",
            title="Transformer Citation Study",
            doi="10.1000/high",
            year=2025,
            authors=["Alice Smith", "Bob Lee"],
        ),
        CitingPaper(
            canonical_id="paper-medium",
            title="Follow-up Analysis of Transparent Models",
            doi="10.1000/variant",
            year=2025,
            authors=["Alice Smith", "Carol Ng"],
        ),
        CitingPaper(
            canonical_id="paper-miss",
            title="No External Work Found",
            doi=None,
            year=2025,
            authors=["Zed Unknown"],
        ),
        CitingPaper(
            canonical_id="paper-no-author-id",
            title="No Author ID Case",
            doi="10.1000/no-author-id",
            year=2025,
            authors=["No Id Author"],
        ),
    ]


def assert_stage4_work_authorship_labels():
    """Assert Stage 4 only profiles authors from trusted work authorships."""
    openalex = FakeOpenAlexWorkClient()
    result = analyze_author_intel(
        citing_papers=build_citing_papers(),
        openalex_client=openalex,
        arxiv_client=FakeArxivClient(),
    )

    assert len(result.author_profiles) == 3, result.author_profiles
    assert len(result.skipped_papers) == 2, result.skipped_papers
    assert {item["citing_paper_id"] for item in result.skipped_papers} == {"paper-miss", "paper-no-author-id"}
    assert all("Zed Unknown" not in profile.name for profile in result.author_profiles), result.author_profiles
    assert all("No Id Author" not in profile.name for profile in result.author_profiles), result.author_profiles
    assert sorted(openalex.author_id_calls) == [
        "https://openalex.org/A1",
        "https://openalex.org/A2",
        "https://openalex.org/A3",
    ], openalex.author_id_calls

    labels = {label.author_id: label for label in result.scholar_labels}
    profiles = {profile.name: profile for profile in result.author_profiles}

    alice_profile = profiles["Alice Smith"]
    alice_label = labels[alice_profile.author_id]
    assert alice_label.label == "heavyweight_candidate", alice_label
    assert "openalex_work_authorship" in alice_profile.evidence_sources, alice_profile
    assert "work_authorship_variant" in alice_profile.evidence_sources, alice_profile

    bob_profile = profiles["Bob Lee"]
    bob_label = labels[bob_profile.author_id]
    assert bob_label.label == "high_impact_candidate", bob_label

    carol_profile = profiles["Carol Ng"]
    carol_label = labels[carol_profile.author_id]
    assert carol_label.label == "weak_signal_candidate", carol_label
    assert carol_label.confidence_note == "evidence_insufficient_missing_h_index", carol_label

    assert result.author_summary.total_authors == 3
    assert result.author_summary.matched_profiles == 3
    assert result.author_summary.heavyweight_candidates == 1
    assert result.author_summary.high_impact_candidates == 1
    assert result.author_summary.weak_signal_candidates == 1
    return result


def main() -> None:
    """Run Stage 4 author-intelligence assertions."""
    logger = StageLogger("stage4")
    logger.start()
    result = assert_stage4_work_authorship_labels()
    logger.pass_case(
        "work_authorship_author_intel",
        detail=(
            f"citing_papers={len(build_citing_papers())} authors={len(result.author_profiles)} "
            f"skipped={len(result.skipped_papers)} heavyweight={result.author_summary.heavyweight_candidates} "
            f"high_impact={result.author_summary.high_impact_candidates} "
            f"weak_signal={result.author_summary.weak_signal_candidates}"
        ),
    )
    logger.done("stage4 validation passed")


if __name__ == "__main__":
    main()
