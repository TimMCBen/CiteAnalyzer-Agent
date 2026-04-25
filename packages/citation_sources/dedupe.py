from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List

from packages.citation_sources.models import CitingPaper, SourceTrace


def merge_normalized_records(records: Iterable[Dict[str, object]]) -> tuple[List[CitingPaper], List[SourceTrace]]:
    deduped_papers: List[CitingPaper] = []
    source_traces: List[SourceTrace] = []
    seen_by_doi: Dict[str, int] = {}
    seen_by_title_key: Dict[str, int] = {}
    fetched_at = datetime.now(timezone.utc).isoformat()

    for record in records:
        merge_status = "unique"
        record_key = _title_year_key(record)
        doi = record.get("doi")

        if isinstance(doi, str) and doi in seen_by_doi:
            index = seen_by_doi[doi]
            merge_status = "doi"
        elif record_key and record_key in seen_by_title_key:
            index = seen_by_title_key[record_key]
            merge_status = "heuristic"
        else:
            index = len(deduped_papers)
            deduped_papers.append(_create_citing_paper(record, index))
            if isinstance(doi, str):
                seen_by_doi[doi] = index
            if record_key:
                seen_by_title_key[record_key] = index

        if merge_status != "unique":
            _merge_into_citing_paper(deduped_papers[index], record)

        source_traces.append(
            SourceTrace(
                candidate_id=deduped_papers[index].canonical_id,
                source_name=str(record.get("source_name") or "unknown"),
                source_record_id=str(record.get("source_record_id") or ""),
                query_used=str(record.get("query_used") or ""),
                fetched_at=fetched_at,
                raw_title=str(record.get("title") or ""),
                raw_doi=str(record.get("doi") or ""),
                merge_status=merge_status,
            )
        )

    for paper in deduped_papers:
        paper.source_names.sort()

    return deduped_papers, source_traces


def _create_citing_paper(record: Dict[str, object], index: int) -> CitingPaper:
    paper = CitingPaper(
        canonical_id=f"citing-{index + 1}",
        title=str(record.get("title") or ""),
        doi=record.get("doi") if isinstance(record.get("doi"), str) else None,
        year=record.get("year") if isinstance(record.get("year"), int) else None,
        authors=list(record.get("authors") or []),
        venue=record.get("venue") if isinstance(record.get("venue"), str) else None,
        abstract=record.get("abstract") if isinstance(record.get("abstract"), str) else None,
    )
    _merge_into_citing_paper(paper, record)
    return paper


def _merge_into_citing_paper(paper: CitingPaper, record: Dict[str, object]) -> None:
    source_name = str(record.get("source_name") or "unknown")
    source_record_id = str(record.get("source_record_id") or "")
    source_url = str(record.get("url") or "")
    title = str(record.get("title") or "")
    venue = record.get("venue") if isinstance(record.get("venue"), str) else None
    abstract = record.get("abstract") if isinstance(record.get("abstract"), str) else None
    year = record.get("year") if isinstance(record.get("year"), int) else None
    doi = record.get("doi") if isinstance(record.get("doi"), str) else None
    authors = [author for author in list(record.get("authors") or []) if isinstance(author, str)]

    if source_name not in paper.source_names:
        paper.source_names.append(source_name)
    if source_record_id:
        paper.source_specific_ids[source_name] = source_record_id
    if source_url:
        paper.source_links[source_name] = source_url
    if not paper.title and title:
        paper.title = title
    if not paper.venue and venue:
        paper.venue = venue
    if not paper.abstract and abstract:
        paper.abstract = abstract
    if paper.year is None and year is not None:
        paper.year = year
    if not paper.doi and doi:
        paper.doi = doi
    if not paper.authors and authors:
        paper.authors = authors


def _title_year_key(record: Dict[str, object]) -> str:
    normalized_title = str(record.get("normalized_title") or "")
    year = record.get("year")
    authors = record.get("authors") or []
    first_author = authors[0].casefold() if authors else ""
    if not normalized_title:
        return ""
    return f"{normalized_title}|{year}|{first_author}"
