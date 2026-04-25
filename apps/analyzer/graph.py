from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from apps.analyzer.nodes import parse_user_query
from packages.shared.models import AnalysisState


def build_stage1_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", END)
    return graph.compile()
