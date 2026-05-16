from __future__ import annotations

from pathlib import Path

import requests

from apps.analyzer.config import get_grobid_api_url
from packages.shared.runtime_logging import get_runtime_logger

REQUEST_TIMEOUT_SECONDS = 240


def grobid_is_alive(base_url: str | None = None) -> bool:
    api_url = (base_url or get_grobid_api_url()).rstrip("/")
    get_runtime_logger().detail("grobid.health", "正在检查 GROBID 服务", url=api_url)
    response = requests.get(f"{api_url}/isalive", timeout=30)
    response.raise_for_status()
    alive = response.text.strip().lower() == "true"
    get_runtime_logger().detail("grobid.health", "GROBID 健康检查完成", alive=alive, url=api_url)
    return alive


def process_fulltext_document(
    pdf_path: Path,
    output_xml_path: Path | None = None,
    base_url: str | None = None,
) -> Path:
    api_url = (base_url or get_grobid_api_url()).rstrip("/")
    out_path = output_xml_path or pdf_path.with_suffix(".grobid.tei.xml")
    get_runtime_logger().detail("grobid.process", "正在用 GROBID 解析 PDF", pdf=pdf_path)
    with pdf_path.open("rb") as handle:
        response = requests.post(
            f"{api_url}/processFulltextDocument",
            files={"input": handle},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    get_runtime_logger().detail("grobid.process", "GROBID TEI 已保存", tei=out_path)
    return out_path
