from __future__ import annotations

from apps.analyzer.orchestrator import CitationAnalysisAgent
from packages.shared.models import AnalysisRequest, TargetPaper


def run_analysis(paper_input: str) -> TargetPaper:
    request = AnalysisRequest(paper_input=paper_input)
    agent = CitationAnalysisAgent()
    return agent.analyze(request)
