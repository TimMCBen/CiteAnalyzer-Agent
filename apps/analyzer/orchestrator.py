from __future__ import annotations

from packages.shared.models import AnalysisRequest, TargetPaper


class CitationAnalysisAgent:
    def analyze(self, request: AnalysisRequest) -> TargetPaper:
        raise NotImplementedError("Stage 1 orchestration flow is not implemented yet.")
