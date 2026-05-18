"""Validate shared retry behavior and client retry integration."""
from __future__ import annotations

import contextlib
import io
import ssl
import sys
from pathlib import Path
from urllib import error


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.shared.network_retry import RetryExhaustedError, RetryPolicy, retry_call
from packages.shared.runtime_logging import RuntimeLogger, runtime_context
from scripts.test_agent.stage_logging import StageLogger


def assert_retry_then_success() -> None:
    calls = 0
    sleeps: list[float] = []
    output = io.StringIO()

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ssl.SSLError("simulated TLS EOF")
        return "ok"

    policy = RetryPolicy(
        service="openalex",
        operation="lookup_author",
        max_attempts=3,
        base_delay_seconds=0.1,
        jitter_seconds=0.0,
        impact="single_author",
    )
    with contextlib.redirect_stdout(output), runtime_context(logger=RuntimeLogger(mode="detail")):
        result = retry_call(flaky, policy, sleeper=sleeps.append)

    assert result == "ok"
    assert calls == 2, calls
    assert sleeps == [0.1], sleeps
    text = output.getvalue()
    assert "DETAIL retry.wait" in text, text
    assert "service=openalex" in text, text
    assert "reason=SSLError" in text, text


def assert_non_retryable_http_status_fails_fast() -> None:
    calls = 0
    sleeps: list[float] = []

    def missing() -> None:
        nonlocal calls
        calls += 1
        raise error.HTTPError("https://example.test/missing", 404, "not found", hdrs={}, fp=None)

    try:
        retry_call(
            missing,
            RetryPolicy(service="crossref", operation="fetch", max_attempts=3, jitter_seconds=0.0),
            sleeper=sleeps.append,
        )
    except error.HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("expected HTTPError 404")

    assert calls == 1, calls
    assert sleeps == [], sleeps


def assert_retry_after_controls_delay() -> None:
    calls = 0
    sleeps: list[float] = []

    class Headers(dict):
        """Header mapping used to exercise Retry-After parsing."""
        def get(self, key, default=None):
            """Return header values using the mapping interface."""
            return super().get(key, default)

    def rate_limited() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error.HTTPError(
                "https://example.test/rate-limit",
                429,
                "rate limited",
                hdrs=Headers({"Retry-After": "1.5"}),
                fp=None,
            )
        return "ok"

    result = retry_call(
        rate_limited,
        RetryPolicy(
            service="semantic_scholar",
            operation="fetch",
            max_attempts=2,
            base_delay_seconds=0.1,
            max_delay_seconds=4.0,
            jitter_seconds=0.0,
        ),
        sleeper=sleeps.append,
    )

    assert result == "ok"
    assert sleeps == [1.5], sleeps


def assert_exhaustion_is_structured_and_logged() -> None:
    calls = 0
    sleeps: list[float] = []
    output = io.StringIO()

    def down() -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError("simulated timeout")

    with contextlib.redirect_stdout(output), runtime_context(logger=RuntimeLogger(mode="detail")):
        try:
            retry_call(
                down,
                RetryPolicy(
                    service="grobid",
                    operation="health",
                    max_attempts=2,
                    base_delay_seconds=0.2,
                    jitter_seconds=0.0,
                ),
                sleeper=sleeps.append,
            )
        except RetryExhaustedError as exc:
            assert exc.policy.service == "grobid"
            assert exc.attempts == 2
            assert exc.reason == "TimeoutError"
        else:
            raise AssertionError("expected RetryExhaustedError")

    assert calls == 2, calls
    assert sleeps == [0.2], sleeps
    text = output.getvalue()
    assert "WARN retry.exhausted" in text, text
    assert "service=grobid" in text, text


def assert_openalex_client_retries_tls_disconnect() -> None:
    import packages.author_intel.clients.openalex as openalex_module

    calls = 0
    original_urlopen = openalex_module.request.urlopen

    class FakeResponse:
        """Test double that simulates fake response behavior."""
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            """Return a fake OpenAlex response body."""
            return (
                b'{"results":[{"id":"https://openalex.org/A1","display_name":"Lei Bai",'
                b'"summary_stats":{"h_index":31},"cited_by_count":500,"works_count":40}]}'
            )

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ssl.SSLError("TLS EOF")
        return FakeResponse()

    try:
        openalex_module.request.urlopen = fake_urlopen
        client = openalex_module.OpenAlexClient(max_attempts=2, retry_base_delay_seconds=0, retry_jitter_seconds=0)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), runtime_context(logger=RuntimeLogger(mode="detail")):
            record = client.lookup_author("Lei Bai")
    finally:
        openalex_module.request.urlopen = original_urlopen

    assert calls == 2, calls
    assert record is not None
    assert record["h_index"] == 31, record
    assert "DETAIL retry.wait" in output.getvalue(), output.getvalue()


def assert_dblp_client_retries_transient_failure() -> None:
    import packages.author_intel.clients.dblp as dblp_module

    calls = 0
    original_urlopen = dblp_module.request.urlopen

    class FakeResponse:
        """Test double that simulates fake response behavior."""
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            """Return a fake DBLP response body."""
            return b'{"result":{"hits":{"hit":[{"info":{"author":"Lei Bai","url":"https://dblp.org/pid/x/y"}}]}}}'

    def fake_urlopen(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary timeout")
        return FakeResponse()

    try:
        dblp_module.request.urlopen = fake_urlopen
        client = dblp_module.DBLPClient(max_attempts=2, retry_base_delay_seconds=0, retry_jitter_seconds=0)
        record = client.lookup_author("Lei Bai")
    finally:
        dblp_module.request.urlopen = original_urlopen

    assert calls == 2, calls
    assert record is not None
    assert record["source_ids"] == {"dblp": "https://dblp.org/pid/x/y"}, record


def main() -> None:
    """Run retry-policy and transient-client contract assertions."""
    logger = StageLogger("network_retry")
    logger.start()
    assert_retry_then_success()
    logger.pass_case("retry_then_success")
    assert_non_retryable_http_status_fails_fast()
    logger.pass_case("non_retryable_http_status_fails_fast")
    assert_retry_after_controls_delay()
    logger.pass_case("retry_after_controls_delay")
    assert_exhaustion_is_structured_and_logged()
    logger.pass_case("exhaustion_is_structured_and_logged")
    assert_openalex_client_retries_tls_disconnect()
    logger.pass_case("openalex_client_retries_tls_disconnect")
    assert_dblp_client_retries_transient_failure()
    logger.pass_case("dblp_client_retries_transient_failure")
    logger.done("network retry contract passed")


if __name__ == "__main__":
    main()
