from __future__ import annotations

import random
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar
from urllib import error

from packages.shared.runtime_logging import get_runtime_logger

try:
    import requests
except ImportError:  # pragma: no cover - requests is an app dependency, keep helper import-safe.
    requests = None  # type: ignore[assignment]


DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    service: str
    operation: str
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.25
    retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES
    overall_budget_seconds: float | None = None
    impact: str | None = None


@dataclass(frozen=True)
class RetryDecision:
    retryable: bool
    reason: str
    status: int | None = None
    retry_after_seconds: float | None = None


class RetryExhaustedError(RuntimeError):
    def __init__(self, policy: RetryPolicy, attempts: int, last_error: BaseException, decision: RetryDecision):
        self.policy = policy
        self.attempts = attempts
        self.last_error = last_error
        self.status = decision.status
        self.reason = decision.reason
        message = (
            f"{policy.service}.{policy.operation} exhausted retry attempts "
            f"attempts={attempts} reason={decision.reason} error_type={last_error.__class__.__name__}"
        )
        super().__init__(message)


def retry_call(
    func: Callable[[], T],
    policy: RetryPolicy,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    logger: Any | None = None,
) -> T:
    max_attempts = max(1, policy.max_attempts)
    active_logger = logger or get_runtime_logger()
    started_at = monotonic()

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as exc:
            decision = classify_retryable_error(exc, policy)
            if not decision.retryable:
                raise
            if attempt >= max_attempts:
                _log_exhausted(active_logger, policy, attempt, decision)
                raise RetryExhaustedError(policy, attempt, exc, decision) from exc

            delay = _compute_delay(policy, attempt, decision)
            if policy.overall_budget_seconds is not None:
                elapsed = monotonic() - started_at
                if elapsed + delay > policy.overall_budget_seconds:
                    _log_exhausted(active_logger, policy, attempt, decision)
                    raise RetryExhaustedError(policy, attempt, exc, decision) from exc

            active_logger.detail(
                "retry.wait",
                f"{policy.service} {policy.operation} 遇到瞬时网络异常，将在等待后重试",
                service=policy.service,
                operation=policy.operation,
                attempt=attempt,
                max_attempts=max_attempts,
                delay_s=f"{delay:.2f}",
                reason=decision.reason,
                status=decision.status,
                retry_after_s=(
                    f"{decision.retry_after_seconds:.2f}" if decision.retry_after_seconds is not None else None
                ),
                impact=policy.impact,
            )
            if delay > 0:
                sleeper(delay)

    raise AssertionError("unreachable retry loop state")


def classify_retryable_error(exc: BaseException, policy: RetryPolicy) -> RetryDecision:
    status = _http_status(exc)
    retry_after = _retry_after_seconds(exc)
    if status is not None:
        return RetryDecision(
            retryable=status in policy.retry_statuses,
            reason=f"http_{status}",
            status=status,
            retry_after_seconds=retry_after,
        )

    if _is_transient_network_error(exc):
        return RetryDecision(retryable=True, reason=exc.__class__.__name__)

    return RetryDecision(retryable=False, reason=exc.__class__.__name__)


def _http_status(exc: BaseException) -> int | None:
    if isinstance(exc, error.HTTPError):
        return int(exc.code)
    if requests is not None and isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        if response is not None and response.status_code is not None:
            return int(response.status_code)
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _retry_after_seconds(exc: BaseException) -> float | None:
    headers = None
    if isinstance(exc, error.HTTPError):
        headers = exc.headers
    elif requests is not None and isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)

    if not headers:
        return None
    retry_after = headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        return max(float(retry_after), 0.0)
    except (TypeError, ValueError):
        return None


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout, ssl.SSLError, error.URLError)):
        return True
    if requests is not None and isinstance(
        exc,
        (
            requests.Timeout,
            requests.ConnectionError,
            requests.SSLError,
        ),
    ):
        return True
    if isinstance(exc, OSError):
        text = str(exc).lower()
        return any(marker in text for marker in ("tls", "ssl", "eof", "connection reset", "timed out"))
    class_name = exc.__class__.__name__.lower()
    return any(
        marker in class_name
        for marker in (
            "apiconnectionerror",
            "apitimeouterror",
            "internalservererror",
            "ratelimiterror",
            "serviceunavailable",
            "timeout",
        )
    )


def _compute_delay(policy: RetryPolicy, attempt: int, decision: RetryDecision) -> float:
    if decision.retry_after_seconds is not None:
        return min(decision.retry_after_seconds, policy.max_delay_seconds)
    exponential = policy.base_delay_seconds * (2 ** max(attempt - 1, 0))
    capped = min(exponential, policy.max_delay_seconds)
    if policy.jitter_seconds <= 0:
        return capped
    return capped + random.uniform(0.0, policy.jitter_seconds)


def _log_exhausted(logger: Any, policy: RetryPolicy, attempts: int, decision: RetryDecision) -> None:
    logger.warn(
        "retry.exhausted",
        f"{policy.service} {policy.operation} 多次失败，已达到重试上限或预算限制",
        service=policy.service,
        operation=policy.operation,
        attempts=attempts,
        reason=decision.reason,
        status=decision.status,
        impact=policy.impact,
    )
