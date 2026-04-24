from __future__ import annotations

from apps.analyzer.orchestrator import CitationAnalysisAgent
from packages.shared.models import AnalysisRequest


def run_analysis(paper_input: str) -> None:
    request = AnalysisRequest(paper_input=paper_input)
    agent = CitationAnalysisAgent()
    agent.analyze(request)
