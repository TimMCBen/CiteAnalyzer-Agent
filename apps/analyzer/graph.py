from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from apps.analyzer.nodes import fetch_citation_candidates_node, parse_user_query, resolve_target_paper_node
from packages.shared.models import AnalysisState


def build_stage1_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_node("resolve_target_paper", resolve_target_paper_node)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", "resolve_target_paper")
    graph.add_edge("resolve_target_paper", END)
    return graph.compile()


def build_stage2_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_node("resolve_target_paper", resolve_target_paper_node)
    graph.add_node("fetch_citation_candidates", fetch_citation_candidates_node)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", "resolve_target_paper")
    graph.add_edge("resolve_target_paper", "fetch_citation_candidates")
    graph.add_edge("fetch_citation_candidates", END)
    return graph.compile()
