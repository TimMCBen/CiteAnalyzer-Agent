from __future__ import annotations

from apps.analyzer.resolve import resolve_target_paper
from packages.shared.models import AnalysisRequest, TargetPaper


class CitationAnalysisAgent:
    def analyze(self, request: AnalysisRequest) -> TargetPaper:
        return resolve_target_paper(request.paper_input)

    def crawl_citations(self, target_paper: TargetPaper) -> None:
        raise NotImplementedError("Stage 2 citation crawling is not implemented yet.")
