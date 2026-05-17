"""Command-line validation helpers for paper identity."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.paper_identity.clients.arxiv import ArxivMetadataClient
from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient, _redact_url
from packages.paper_identity.models import CandidateAuthor, CandidateWork, LLMIdentityReview, PaperIdentityEvidence
from packages.paper_identity.rules import decide_paper_identity, merge_llm_review
from packages.paper_identity.service import resolve_paper_identity
from scripts.eval.paper_identity_score import read_jsonl, score_predictions
from scripts.test_agent.stage_logging import StageLogger


ARXIV_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2504.19162v1</id>
    <title>SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning</title>
    <author><name>Lei Bai</name></author>
    <author><name>Example Coauthor</name></author>
  </entry>
</feed>
"""


def work(
    title: str,
    *,
    work_id: str = "https://openalex.org/W1",
    doi: str | None = "10.1234/example",
    year: int | None = 2025,
    authors: list[str] | None = None,
    source: str = "openalex",
) -> CandidateWork:
    """Build a candidate work fixture for stage validation."""
    return CandidateWork(
        source=source,
        work_id=work_id,
        title=title,
        doi=doi,
        year=year,
        authors=[
            CandidateAuthor(name=name, author_id=f"https://openalex.org/A{index}")
            for index, name in enumerate(authors or ["Alice Chen", "Bob Lee"], start=1)
        ],
    )


def assert_rule_decisions() -> dict[str, str]:
    title = "SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning"

    doi_verified = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="doi-ok",
            title=title,
            doi="10.1234/example",
            year=2025,
            authors=["Alice Chen", "Bob Lee"],
            doi_work=work(title),
        )
    )
    assert doi_verified.paper_match_confidence == "high", doi_verified
    assert doi_verified.doi_status == "present_verified", doi_verified
    assert doi_verified.author_resolution_status == "work_authorship_verified", doi_verified

    doi_mismatch = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="doi-bad",
            title=title,
            doi="10.1234/wrong",
            year=2025,
            authors=["Alice Chen", "Bob Lee"],
            doi_work=work("A Completely Different Survey of Database Indexes"),
        )
    )
    assert doi_mismatch.doi_status == "present_mismatch", doi_mismatch
    assert "doi_title_mismatch" in doi_mismatch.source_conflicts, doi_mismatch
    assert doi_mismatch.paper_match_confidence in {"miss", "low"}, doi_mismatch

    title_verified = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="title-ok",
            title=title,
            year=2025,
            authors=["Alice Chen", "Bob Lee"],
            title_work_candidates=[work(title, doi=None)],
        )
    )
    assert title_verified.paper_match_confidence == "high", title_verified
    assert title_verified.openalex_work_status == "title_hit_verified", title_verified

    author_count_anomaly = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="author-count",
            title=title,
            year=2025,
            authors=["Alice Chen", "Bob Lee"],
            title_work_candidates=[work(title, authors=[f"Unrelated Author {i}" for i in range(10)])],
        )
    )
    assert author_count_anomaly.paper_match_confidence == "medium", author_count_anomaly
    assert "author_count_mismatch" in author_count_anomaly.source_conflicts, author_count_anomaly
    assert author_count_anomaly.needs_llm_review is True, author_count_anomaly

    lookup_error = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="error",
            title=title,
            doi="10.1234/example",
            errors=["openalex_doi:TimeoutError:boom", "arxiv_title:TimeoutError:boom"],
        )
    )
    assert lookup_error.paper_match_confidence == "error", lookup_error
    assert lookup_error.needs_llm_review is False, lookup_error

    arxiv_only = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="arxiv-only",
            title=title,
            year=2025,
            authors=["Alice Chen", "Bob Lee"],
            arxiv_candidates=[work(title, doi="10.48550/arXiv.2504.19162", source="arxiv")],
        )
    )
    assert arxiv_only.paper_match_confidence == "high", arxiv_only
    assert arxiv_only.selected_work_source == "arxiv_verified", arxiv_only
    assert arxiv_only.openalex_work_status == "no_result", arxiv_only
    assert arxiv_only.arxiv_status == "present_verified", arxiv_only

    return {
        "doi_verified": doi_verified.paper_match_confidence,
        "doi_mismatch": doi_mismatch.doi_status,
        "title_verified": title_verified.openalex_work_status,
        "author_count_anomaly": author_count_anomaly.paper_match_confidence,
        "lookup_error": lookup_error.paper_match_confidence,
        "arxiv_only": arxiv_only.selected_work_source,
    }


def assert_llm_hard_constraints() -> dict[str, str]:
    title = "SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning"
    low_decision = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="low-title",
            title=title,
            authors=["Alice Chen"],
            title_work_candidates=[work("A Completely Different Survey of Database Indexes", authors=["Unrelated Person"])],
        )
    )
    low_decision.llm_review = LLMIdentityReview(
        paper_identity_decision="same_paper",
        paper_confidence="high",
        needs_manual_review=False,
        reason_zh="baseline 测试：模型试图在低相似度证据上升高置信。",
    )
    merged_low = merge_llm_review(low_decision)
    assert merged_low.paper_match_confidence != "high", merged_low

    no_author_id_decision = decide_paper_identity(
        PaperIdentityEvidence(
            citing_paper_id="no-author-id",
            title=title,
            authors=["Alice Chen", "Bob Lee"],
            title_work_candidates=[
                CandidateWork(
                    source="openalex",
                    work_id="https://openalex.org/W-no-author-id",
                    title=title,
                    authors=[CandidateAuthor(name="Alice Chen"), CandidateAuthor(name="Bob Lee")],
                )
            ],
        )
    )
    assert no_author_id_decision.author_resolution_status == "weak_signal_only", no_author_id_decision
    no_author_id_decision.llm_review = LLMIdentityReview(
        paper_identity_decision="same_paper",
        paper_confidence="high",
        author_confidence="high",
        needs_manual_review=False,
        reason_zh="baseline 测试：模型试图在无 author.id 时声称作者高置信。",
    )
    merged_no_author = merge_llm_review(no_author_id_decision)
    assert merged_no_author.paper_match_confidence == "high", merged_no_author
    assert merged_no_author.author_resolution_status == "weak_signal_only", merged_no_author

    return {
        "low_title_after_llm": merged_low.paper_match_confidence,
        "no_author_id_status": merged_no_author.author_resolution_status,
    }


def assert_arxiv_cache_and_throttle() -> dict[str, object]:
    calls: list[str] = []
    slept: list[float] = []
    clock = {"now": 10.0}

    def fake_fetcher(url: str) -> str:
        calls.append(url)
        return ARXIV_FIXTURE

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["now"] += seconds

    client = ArxivMetadataClient(
        min_interval_seconds=3.1,
        fetcher=fake_fetcher,
        sleeper=fake_sleep,
        monotonic=lambda: clock["now"],
    )

    first = client.search_by_title("SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning")
    second = client.search_by_title("SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning")
    assert len(first) == 1 and len(second) == 1, (first, second)
    assert client.request_count == 1, client.request_count
    assert client.cache_hits == 1, client.cache_hits

    ids = client.lookup_ids(["2504.19162", "2504.19162v1"])
    assert len(ids) == 1, ids
    assert client.request_count == 2, client.request_count
    assert client.http_attempt_count == 2, client.http_attempt_count
    assert slept and slept[0] >= 3.0, slept

    return {
        "requests": client.request_count,
        "http_attempts": client.http_attempt_count,
        "cache_hits": client.cache_hits,
        "slept": [round(item, 2) for item in slept],
    }


def assert_arxiv_error_does_not_poison_cache() -> dict[str, object]:
    calls = 0

    def flaky_fetcher(url: str) -> str:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise TimeoutError("temporary")
        return ARXIV_FIXTURE

    client = ArxivMetadataClient(
        min_interval_seconds=0,
        fetcher=flaky_fetcher,
        sleeper=lambda seconds: None,
        monotonic=lambda: 1.0,
    )
    try:
        client.search_by_title("SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning")
    except Exception:
        pass
    else:
        raise AssertionError("expected first arXiv lookup to fail")

    works = client.search_by_title("SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning")
    assert len(works) == 1, works
    assert calls == 3, calls
    assert client.http_attempt_count == 3, client.http_attempt_count
    assert client.cache_hits == 0, client.cache_hits
    return {"calls": calls, "http_attempts": client.http_attempt_count, "works": len(works), "cache_hits": client.cache_hits}


def assert_openalex_work_auth_params() -> dict[str, object]:
    client = OpenAlexWorkClient(api_key="oa-test-key", mailto="owner@example.com")
    url = client._build_url("/works", {"search": "test paper", "per-page": "3"})
    assert "api_key=oa-test-key" in url, url
    assert "mailto=owner%40example.com" in url, url
    redacted = _redact_url(url)
    assert "oa-test-key" not in redacted, redacted
    assert "owner%40example.com" not in redacted, redacted
    return {"has_api_key": "api_key=oa-test-key" in url, "redacted": "[REDACTED]" in redacted}


class FakeUrlopenResponse:
    """Test double that simulates fake urlopen response behavior."""
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        """Read read for fake urlopen response."""
        return b'{"results":[]}'


def assert_openalex_http_attempt_count_tracks_retries() -> dict[str, object]:
    import packages.paper_identity.clients.openalex_work as openalex_work_module

    calls = 0
    original_urlopen = openalex_work_module.request.urlopen

    def flaky_urlopen(req, timeout: float):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise TimeoutError("temporary")
        return FakeUrlopenResponse()

    client = OpenAlexWorkClient(max_attempts=3, retry_base_delay_seconds=0, retry_jitter_seconds=0)
    openalex_work_module.request.urlopen = flaky_urlopen
    try:
        result = client.search_work_by_title("temporary retry paper")
    finally:
        openalex_work_module.request.urlopen = original_urlopen

    assert result == [], result
    assert calls == 3, calls
    assert client.request_count == 3, client.request_count
    assert client.http_attempt_count == 3, client.http_attempt_count
    return {"calls": calls, "http_attempts": client.http_attempt_count}


class FakeOpenAlexClient:
    """Client wrapper for fake open alex operations used by stage validation."""
    def __init__(self) -> None:
        self.doi_calls = 0
        self.title_calls = 0

    def lookup_work_by_doi(self, doi: str | None) -> CandidateWork | None:
        """Look up work by doi for fake open alex client."""
        self.doi_calls += 1
        return None

    def search_work_by_title(self, title: str, *, per_page: int = 3) -> list[CandidateWork]:
        """Search work by title for fake open alex client."""
        self.title_calls += 1
        return [work(title, doi=None, authors=["Lei Bai", "Example Coauthor"])]


class FakeArxivClient:
    """Client wrapper for fake arXiv operations used by stage validation."""
    def __init__(self) -> None:
        self.id_calls = 0
        self.title_calls = 0

    def lookup_ids(self, arxiv_ids: list[str]) -> list[CandidateWork]:
        """Look up ids for fake arXiv client."""
        self.id_calls += 1
        return [work("SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning", source="arxiv")]

    def search_by_title(self, title: str, *, max_results: int = 3) -> list[CandidateWork]:
        """Search by title for fake arXiv client."""
        self.title_calls += 1
        return [work(title, source="arxiv")]


def assert_sidecar_resolution() -> dict[str, object]:
    paper = CitingPaper(
        canonical_id="citing-spc",
        title="SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning",
        doi=None,
        year=2025,
        authors=["Lei Bai", "Example Coauthor"],
        source_links={"s2": "https://arxiv.org/abs/2504.19162"},
    )
    openalex = FakeOpenAlexClient()
    arxiv = FakeArxivClient()

    decision = resolve_paper_identity(
        paper,
        openalex_client=openalex,
        arxiv_client=arxiv,
        use_llm_review=False,
    )

    assert decision.paper_match_confidence == "high", decision
    assert decision.openalex_work_status == "title_hit_verified", decision
    assert decision.arxiv_status == "present_verified", decision
    assert arxiv.id_calls == 1 and arxiv.title_calls == 0, (arxiv.id_calls, arxiv.title_calls)
    return {
        "confidence": decision.paper_match_confidence,
        "openalex_status": decision.openalex_work_status,
        "arxiv_status": decision.arxiv_status,
        "arxiv_id_calls": arxiv.id_calls,
        "arxiv_title_calls": arxiv.title_calls,
    }


def assert_eval_scoring_normalizes_arxiv_and_counts_api() -> dict[str, object]:
    gold = [
        {
            "s2_paper_id": "p1",
            "gold_identity_label": "same_paper",
            "gold_arxiv_id": "2504.19162",
            "gold_doi_status": "present_mismatch",
        }
    ]
    predictions = [
        {
            "s2_paper_id": "p1",
            "paper_identity_decision": "same_paper",
            "selected_work_id": "https://arxiv.org/abs/2504.19162",
            "doi_status": "present_mismatch",
            "llm_call_count": 1,
            "api_call_count": 2,
        }
    ]
    summary = score_predictions(gold, predictions)
    assert summary.selected_work_accuracy == 1.0, summary
    assert summary.api_call_count == 2, summary

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "gold.jsonl"
        path.write_bytes(
            b"\xef\xbb\xbf"
            + b'{"s2_paper_id":"p1","gold_identity_label":"same_paper","gold_arxiv_id":"2504.19162"}\n'
        )
        assert len(read_jsonl(path)) == 1

    return {"selected_work_accuracy": summary.selected_work_accuracy, "api_call_count": summary.api_call_count}


def main() -> None:
    """Run this module as a command-line validation or utility entry point."""
    logger = StageLogger("paper_identity")
    logger.start()
    rule_summary = assert_rule_decisions()
    logger.pass_case("rule_decisions", detail=str(rule_summary))
    llm_constraints = assert_llm_hard_constraints()
    logger.pass_case("llm_hard_constraints", detail=str(llm_constraints))
    arxiv_summary = assert_arxiv_cache_and_throttle()
    logger.pass_case("arxiv_cache_and_throttle", detail=str(arxiv_summary))
    arxiv_error_cache = assert_arxiv_error_does_not_poison_cache()
    logger.pass_case("arxiv_error_does_not_poison_cache", detail=str(arxiv_error_cache))
    openalex_auth = assert_openalex_work_auth_params()
    logger.pass_case("openalex_work_auth_params", detail=str(openalex_auth))
    openalex_attempts = assert_openalex_http_attempt_count_tracks_retries()
    logger.pass_case("openalex_http_attempt_count", detail=str(openalex_attempts))
    sidecar_summary = assert_sidecar_resolution()
    logger.pass_case("sidecar_resolution", detail=str(sidecar_summary))
    eval_summary = assert_eval_scoring_normalizes_arxiv_and_counts_api()
    logger.pass_case("eval_scoring", detail=str(eval_summary))
    logger.done("paper identity validation passed")


if __name__ == "__main__":
    main()
