from __future__ import annotations

import re
from copy import deepcopy
from typing import Dict, Iterable, List


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    lowered = title.casefold()
    collapsed = re.sub(r"\s+", " ", lowered)
    stripped = re.sub(r"[^a-z0-9 ]+", "", collapsed)
    return stripped.strip()


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower()


def normalize_authors(authors: Iterable[str] | None) -> List[str]:
    if not authors:
        return []
    return [author.strip() for author in authors if author and author.strip()]


def normalize_source_record(record: Dict[str, object], query_used: str) -> Dict[str, object]:
    normalized = deepcopy(record)
    normalized["title"] = str(record.get("title") or "").strip()
    normalized["doi"] = normalize_doi(record.get("doi") if isinstance(record.get("doi"), str) else None)
    normalized["authors"] = normalize_authors(record.get("authors") if isinstance(record.get("authors"), list) else [])
    normalized["source_name"] = str(record.get("source_name") or "unknown").strip().lower()
    normalized["source_record_id"] = str(record.get("source_record_id") or "").strip()
    normalized["url"] = str(record.get("url") or "").strip()
    normalized["source_names"] = sorted({str(name).strip().lower() for name in list(record.get("source_names") or []) if str(name).strip()})
    normalized["source_links"] = {
        str(source_name).strip().lower(): str(source_url).strip()
        for source_name, source_url in dict(record.get("source_links") or {}).items()
        if str(source_name).strip() and str(source_url).strip()
    }
    normalized["source_specific_ids"] = {
        str(source_name).strip().lower(): str(source_id).strip()
        for source_name, source_id in dict(record.get("source_specific_ids") or {}).items()
        if str(source_name).strip() and str(source_id).strip()
    }
    normalized["query_used"] = query_used
    normalized["normalized_title"] = normalize_title(normalized["title"])
    if normalized["source_name"] and normalized["source_name"] not in normalized["source_names"]:
        normalized["source_names"].append(normalized["source_name"])
    if normalized["source_name"] and normalized["url"] and normalized["source_name"] not in normalized["source_links"]:
        normalized["source_links"][normalized["source_name"]] = normalized["url"]
    if normalized["source_name"] and normalized["source_record_id"] and normalized["source_name"] not in normalized["source_specific_ids"]:
        normalized["source_specific_ids"][normalized["source_name"]] = normalized["source_record_id"]
    return normalized
