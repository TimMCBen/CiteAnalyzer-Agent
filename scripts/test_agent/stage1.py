from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer import nodes
from apps.analyzer.nodes import initialize_state, parse_user_query
from packages.shared.errors import InvalidAnalysisRequestError
from packages.shared.models import UserQuery


CASES = [
    {
        "name": "title_clue_request",
        "query": "帮我分析一下 Attention Is All You Need 的被引情况",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "title",
        "expected_paper_query": "Attention Is All You Need",
        "expected_resolve_status": "uncertain",
    },
    {
        "name": "doi_request",
        "query": "请查看 DOI 为 10.1145/3368089.3409740 的论文有哪些施引文献",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "doi",
        "expected_paper_query": "10.1145/3368089.3409740",
        "expected_resolve_status": "resolved",
    },
    {
        "name": "arxiv_request",
        "query": "分析一下这篇 arXiv 论文 https://arxiv.org/abs/1706.03762 的引用情感",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "arxiv",
        "expected_paper_query": "1706.03762",
        "expected_resolve_status": "resolved",
    },
    {
        "name": "openalex_request",
        "query": "我想知道 openalex:W2741809807 这篇论文的主要引用者和情感倾向",
        "expected_request_type": "citation_analysis",
        "expected_query_type": "paper_id",
        "expected_paper_query": "W2741809807",
        "expected_resolve_status": "resolved",
    },
]

INVALID_CASE = {
    "name": "unsupported_request",
    "query": "帮我总结一下 LangGraph 是什么",
}


def assert_case(case: dict[str, str]) -> None:
    state = parse_query(case["query"])
    target_paper = state["target_paper"]

    assert state["request_type"] == case["expected_request_type"], (
        f"{case['name']}: expected request_type={case['expected_request_type']}, "
        f"got {state['request_type']}"
    )
    assert target_paper.paper_query_type == case["expected_query_type"], (
        f"{case['name']}: expected paper_query_type={case['expected_query_type']}, "
        f"got {target_paper.paper_query_type}"
    )
    assert target_paper.paper_query == case["expected_paper_query"], (
        f"{case['name']}: expected paper_query={case['expected_paper_query']!r}, "
        f"got {target_paper.paper_query!r}"
    )
    assert target_paper.resolve_status == case["expected_resolve_status"], (
        f"{case['name']}: expected resolve_status={case['expected_resolve_status']}, "
        f"got {target_paper.resolve_status}"
    )


def assert_invalid_case(case: dict[str, str]) -> None:
    try:
        parse_query(case["query"])
    except InvalidAnalysisRequestError:
        return

    raise AssertionError(f"{case['name']}: expected InvalidAnalysisRequestError")


def parse_query(raw_query: str):
    original_parse_with_llm = nodes.parse_with_llm

    def force_fallback(_: str):
        raise RuntimeError("force fallback parser for deterministic stage1 validation")

    nodes.parse_with_llm = force_fallback
    try:
        state = initialize_state(UserQuery(raw_text=raw_query))
        return parse_user_query(state)
    finally:
        nodes.parse_with_llm = original_parse_with_llm


def main() -> None:
    for case in CASES:
        assert_case(case)
        print(f"[PASS] stage1::{case['name']}")

    assert_invalid_case(INVALID_CASE)
    print(f"[PASS] stage1::{INVALID_CASE['name']}")
    print("stage1 validation passed")


if __name__ == "__main__":
    main()
