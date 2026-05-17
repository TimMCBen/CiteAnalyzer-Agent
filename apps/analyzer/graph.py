"""LangGraph builders for the analyzer stage workflows."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from apps.analyzer.nodes import (
    analyze_author_intel_node,
    analyze_citation_sentiments_node,
    fetch_citation_candidates_node,
    fetch_fulltext_documents_node,
    generate_report_node,
    parse_user_query,
    resolve_target_paper_node,
)
from packages.shared.models import AnalysisState


def build_stage1_graph():
    """Build stage1 graph for the analyzer pipeline."""
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_node("resolve_target_paper", resolve_target_paper_node)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", "resolve_target_paper")
    graph.add_edge("resolve_target_paper", END)
    return graph.compile()


def build_stage2_graph():
    """Build stage2 graph for the analyzer pipeline."""
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_node("resolve_target_paper", resolve_target_paper_node)
    graph.add_node("fetch_citation_candidates", fetch_citation_candidates_node)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", "resolve_target_paper")
    graph.add_edge("resolve_target_paper", "fetch_citation_candidates")
    graph.add_edge("fetch_citation_candidates", END)
    return graph.compile()


def build_stage6_graph():
    """Build stage6 graph for the analyzer pipeline."""
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_node("resolve_target_paper", resolve_target_paper_node)
    graph.add_node("fetch_citation_candidates", fetch_citation_candidates_node)
    graph.add_node("analyze_author_intel", analyze_author_intel_node)
    graph.add_node("fetch_fulltext_documents", fetch_fulltext_documents_node)
    graph.add_node("analyze_citation_sentiments", analyze_citation_sentiments_node)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", "resolve_target_paper")
    graph.add_edge("resolve_target_paper", "fetch_citation_candidates")
    graph.add_edge("fetch_citation_candidates", "analyze_author_intel")
    graph.add_edge("analyze_author_intel", "fetch_fulltext_documents")
    graph.add_edge("fetch_fulltext_documents", "analyze_citation_sentiments")
    graph.add_edge("analyze_citation_sentiments", END)
    return graph.compile()


def build_stage7_graph():
    """Build stage7 graph for the analyzer pipeline."""
    graph = StateGraph(AnalysisState)
    graph.add_node("parse_user_query", parse_user_query)
    graph.add_node("resolve_target_paper", resolve_target_paper_node)
    graph.add_node("fetch_citation_candidates", fetch_citation_candidates_node)
    graph.add_node("analyze_author_intel", analyze_author_intel_node)
    graph.add_node("fetch_fulltext_documents", fetch_fulltext_documents_node)
    graph.add_node("analyze_citation_sentiments", analyze_citation_sentiments_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_edge(START, "parse_user_query")
    graph.add_edge("parse_user_query", "resolve_target_paper")
    graph.add_edge("resolve_target_paper", "fetch_citation_candidates")
    graph.add_edge("fetch_citation_candidates", "analyze_author_intel")
    graph.add_edge("analyze_author_intel", "fetch_fulltext_documents")
    graph.add_edge("fetch_fulltext_documents", "analyze_citation_sentiments")
    graph.add_edge("analyze_citation_sentiments", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()
