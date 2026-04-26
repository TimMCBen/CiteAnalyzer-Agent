from __future__ import annotations

from typing import Mapping, Optional

from packages.citation_sources.models import CitingPaper
from packages.sentiment.models import FullTextDocument, TextSourceSelection


def select_text_source(
    citing_paper: CitingPaper,
    provided_documents: Optional[Mapping[str, FullTextDocument]] = None,
) -> TextSourceSelection:
    document = (provided_documents or {}).get(citing_paper.canonical_id)
    if document and document.text.strip():
        return TextSourceSelection(
            citing_paper_id=citing_paper.canonical_id,
            text=document.text,
            source_type=document.source_type,
            source_label=document.source_label,
            evidence_note="text_loaded",
        )

    if citing_paper.abstract and citing_paper.abstract.strip():
        return TextSourceSelection(
            citing_paper_id=citing_paper.canonical_id,
            text=citing_paper.abstract,
            source_type="abstract",
            source_label="citing_paper.abstract",
            evidence_note="fallback_to_abstract_only",
        )

    return TextSourceSelection(
        citing_paper_id=citing_paper.canonical_id,
        text=None,
        source_type="unknown",
        source_label=None,
        evidence_note="no_text_available",
    )
