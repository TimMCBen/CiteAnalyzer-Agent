"""Configuration helpers for analyzer LLM, GROBID, and local environment settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.shared.network_retry import RetryPolicy, retry_call


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ENV_PATH = REPO_ROOT / ".env"


@dataclass(frozen=True)
class LLMEnvConfig:
    """Store LLM environment settings used to construct analyzer model clients."""
    api_key: str
    base_url: str
    model: str
    env_path: Path

LLM_RETRY_POLICY = RetryPolicy(
    service="LLM",
    operation="结构化调用",
    max_attempts=2,
    base_delay_seconds=1.0,
    max_delay_seconds=4.0,
    jitter_seconds=0.2,
    overall_budget_seconds=8.0,
    impact="llm_provider_call",
)


def load_local_env(*, override: bool = False) -> None:
    """Populate process environment variables from the repository-level .env file."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(dotenv_path=LOCAL_ENV_PATH, override=override)


def get_llm_env_config(*, override: bool = False) -> LLMEnvConfig:
    """Return validated LLM connection settings required by analyzer model calls."""
    load_local_env(override=override)

    api_key = (os.getenv("API_KEY") or "").strip()
    base_url = (os.getenv("BASE_URL") or "").strip()
    model = (os.getenv("MODEL") or "").strip()

    if not api_key:
        raise ValueError("API_KEY is required in .env")
    if not base_url:
        raise ValueError("BASE_URL is required in .env")
    if not model:
        raise ValueError("MODEL is required in .env")
    return LLMEnvConfig(api_key=api_key, base_url=base_url, model=model, env_path=LOCAL_ENV_PATH)


def build_llm() -> Any:
    """Create the chat-model client used by structured analyzer prompts."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("LLM dependencies are not installed") from exc

    config = get_llm_env_config(override=True)
    return ChatOpenAI(api_key=config.api_key, base_url=config.base_url, model=config.model, temperature=0)


def invoke_llm_with_retry(structured_llm: Any, messages: list[dict[str, str]], operation: str) -> Any:
    """Invoke a structured LLM call under the shared retry and timeout policy."""
    policy = RetryPolicy(
        service=LLM_RETRY_POLICY.service,
        operation=operation,
        max_attempts=LLM_RETRY_POLICY.max_attempts,
        base_delay_seconds=LLM_RETRY_POLICY.base_delay_seconds,
        max_delay_seconds=LLM_RETRY_POLICY.max_delay_seconds,
        jitter_seconds=LLM_RETRY_POLICY.jitter_seconds,
        overall_budget_seconds=LLM_RETRY_POLICY.overall_budget_seconds,
        impact=LLM_RETRY_POLICY.impact,
    )
    return retry_call(lambda: structured_llm.invoke(messages), policy)


def get_grobid_api_url() -> str:
    """Return the configured GROBID API base URL with a local default."""
    load_local_env()
    return (os.getenv("GROBID_API_URL") or "http://localhost:8070/api").strip().rstrip("/")
