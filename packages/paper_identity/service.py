"""Service helpers for paper identity matching."""
from __future__ import annotations

from typing import Protocol

from packages.citation_sources.models import CitingPaper
from packages.paper_identity.clients.arxiv import ArxivMetadataClient, extract_arxiv_ids_from_links
from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient
from packages.paper_identity.llm_review import review_identity_with_llm
from packages.paper_identity.models import CandidateWork, LLMIdentityReview, PaperIdentityDecision, PaperIdentityEvidence
from packages.paper_identity.rules import decide_paper_identity, merge_llm_review


class OpenAlexWorkClientProtocol(Protocol):
    """Define the protocol expected by paper identity matching services."""
    def lookup_work_by_doi(self, doi: str | None) -> CandidateWork | None:
        ...

    def search_work_by_title(self, title: str, *, per_page: int = 3) -> list[CandidateWork]:
        ...


class ArxivMetadataClientProtocol(Protocol):
    """Define the protocol expected by paper identity matching services."""
    def lookup_ids(self, arxiv_ids: list[str]) -> list[CandidateWork]:
        ...

    def search_by_title(self, title: str, *, max_results: int = 3) -> list[CandidateWork]:
        ...


def resolve_paper_identities(
    citing_papers: list[CitingPaper],
    *,
    openalex_client: OpenAlexWorkClientProtocol | None = None,
    arxiv_client: ArxivMetadataClientProtocol | None = None,
    use_llm_review: bool = False,
) -> dict[str, PaperIdentityDecision]:
    """Resolve paper identities for paper identity matching."""
    active_openalex = openalex_client or OpenAlexWorkClient()
    active_arxiv = arxiv_client or ArxivMetadataClient()
    return {
        paper.canonical_id: resolve_paper_identity(
            paper,
            openalex_client=active_openalex,
            arxiv_client=active_arxiv,
            use_llm_review=use_llm_review,
        )
        for paper in citing_papers
    }


def resolve_paper_identity(
    citing_paper: CitingPaper,
    *,
    openalex_client: OpenAlexWorkClientProtocol,
    arxiv_client: ArxivMetadataClientProtocol,
    use_llm_review: bool = False,
) -> PaperIdentityDecision:
    """Resolve paper identity for paper identity matching."""
    evidence = build_identity_evidence(
        citing_paper,
        openalex_client=openalex_client,
        arxiv_client=arxiv_client,
    )
    decision = decide_paper_identity(evidence)
    if use_llm_review and decision.needs_llm_review:
        decision.llm_review = review_identity_with_llm(evidence, decision)
        decision = merge_llm_review(decision)
    return decision


def build_identity_evidence(
    citing_paper: CitingPaper,
    *,
    openalex_client: OpenAlexWorkClientProtocol,
    arxiv_client: ArxivMetadataClientProtocol,
) -> PaperIdentityEvidence:
    """Build identity evidence for paper identity matching."""
    evidence = PaperIdentityEvidence(
        citing_paper_id=citing_paper.canonical_id,
        title=citing_paper.title,
        doi=citing_paper.doi,
        year=citing_paper.year,
        authors=list(citing_paper.authors),
    )

    link_values = [
        *list(citing_paper.source_links.values()),
        *[str(value) for value in citing_paper.source_specific_ids.values()],
        citing_paper.doi or "",
    ]
    evidence.arxiv_id_hints = extract_arxiv_ids_from_links(link_values)

    if citing_paper.doi:
        try:
            evidence.doi_work = openalex_client.lookup_work_by_doi(citing_paper.doi)
        except Exception as exc:
            evidence.errors.append(f"openalex_doi:{type(exc).__name__}:{exc}")

    if citing_paper.title:
        try:
            evidence.title_work_candidates = openalex_client.search_work_by_title(citing_paper.title, per_page=3)
        except Exception as exc:
            evidence.errors.append(f"openalex_title:{type(exc).__name__}:{exc}")

    if evidence.arxiv_id_hints:
        try:
            evidence.arxiv_candidates = arxiv_client.lookup_ids(evidence.arxiv_id_hints)
        except Exception as exc:
            evidence.errors.append(f"arxiv_id:{type(exc).__name__}:{exc}")
    elif not evidence.title_work_candidates and citing_paper.title:
        try:
            evidence.arxiv_candidates = arxiv_client.search_by_title(citing_paper.title, max_results=3)
        except Exception as exc:
            evidence.errors.append(f"arxiv_title:{type(exc).__name__}:{exc}")

    return evidence
