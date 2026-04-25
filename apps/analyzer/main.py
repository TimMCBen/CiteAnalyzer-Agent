from __future__ import annotations

from apps.analyzer.graph import build_stage1_graph
from apps.analyzer.nodes import initialize_state
from packages.shared.models import AnalysisState, UserQuery


def run_analysis(raw_text: str) -> AnalysisState:
    query = UserQuery(raw_text=raw_text)
    state = initialize_state(query)
    app = build_stage1_graph()
    return app.invoke(state)
