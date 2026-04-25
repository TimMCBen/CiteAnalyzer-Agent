"""Citation source aggregation for stage2."""

from packages.citation_sources.models import CitingPaper, CitationFetchResult, FetchSummary, SourceTrace
from packages.citation_sources.service import attach_fetch_result_to_state, fetch_citation_candidates

__all__ = [
    "attach_fetch_result_to_state",
    "CitingPaper",
    "CitationFetchResult",
    "FetchSummary",
    "fetch_citation_candidates",
    "SourceTrace",
]
