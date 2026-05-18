"""HTTP client for using GROBID in citation-context extraction."""
from __future__ import annotations

from pathlib import Path

import requests

from apps.analyzer.config import get_grobid_api_url
from packages.shared.network_retry import RetryPolicy, retry_call
from packages.shared.runtime_logging import get_runtime_logger

REQUEST_TIMEOUT_SECONDS = 240
GROBID_HEALTH_RETRY = RetryPolicy(
    service="GROBID",
    operation="健康检查",
    max_attempts=3,
    base_delay_seconds=0.5,
    max_delay_seconds=2.0,
    jitter_seconds=0.1,
    overall_budget_seconds=4.0,
    impact="grobid_availability",
)
GROBID_PROCESS_RETRY = RetryPolicy(
    service="GROBID",
    operation="PDF解析",
    max_attempts=2,
    base_delay_seconds=1.0,
    max_delay_seconds=3.0,
    jitter_seconds=0.2,
    overall_budget_seconds=6.0,
    impact="single_pdf",
)


def grobid_is_alive(base_url: str | None = None) -> bool:
    """Return whether the configured GROBID service is reachable before PDF parsing."""
    api_url = (base_url or get_grobid_api_url()).rstrip("/")
    get_runtime_logger().detail("grobid.health", "正在检查 GROBID 服务", url=api_url)
    response = retry_call(
        lambda: _get_health_response(api_url),
        GROBID_HEALTH_RETRY,
    )
    alive = response.text.strip().lower() == "true"
    get_runtime_logger().detail("grobid.health", "GROBID 健康检查完成", alive=alive, url=api_url)
    return alive


def process_fulltext_document(
    pdf_path: Path,
    output_xml_path: Path | None = None,
    base_url: str | None = None,
) -> Path:
    """Send a PDF to GROBID and persist the returned TEI XML artifact."""
    api_url = (base_url or get_grobid_api_url()).rstrip("/")
    out_path = output_xml_path or pdf_path.with_suffix(".grobid.tei.xml")
    get_runtime_logger().detail("grobid.process", "正在用 GROBID 解析 PDF", pdf=pdf_path)
    response = retry_call(
        lambda: _post_fulltext_document(api_url, pdf_path),
        GROBID_PROCESS_RETRY,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    get_runtime_logger().detail("grobid.process", "GROBID TEI 已保存", tei=out_path)
    return out_path


def _get_health_response(api_url: str) -> requests.Response:
    """Request the GROBID health endpoint and require a successful response."""
    response = requests.get(f"{api_url}/isalive", timeout=30)
    response.raise_for_status()
    return response


def _post_fulltext_document(api_url: str, pdf_path: Path) -> requests.Response:
    """Submit a PDF file to GROBID's full-text processing endpoint."""
    with pdf_path.open("rb") as handle:
        response = requests.post(
            f"{api_url}/processFulltextDocument",
            files={"input": handle},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    return response
