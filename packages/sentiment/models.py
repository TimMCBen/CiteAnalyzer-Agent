from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class FullTextDocument:
    citing_paper_id: str
    text: str
    source_type: Literal["fulltext", "markdown", "latex", "html", "pdf", "abstract", "unknown"] = "unknown"
    source_label: Optional[str] = None
    local_path: Optional[str] = None
    raw_path: Optional[str] = None
    extracted_dir: Optional[str] = None


@dataclass
class TextSourceSelection:
    citing_paper_id: str
    text: Optional[str]
    source_type: Literal["fulltext", "markdown", "latex", "html", "pdf", "abstract", "unknown"] = "unknown"
    source_label: Optional[str] = None
    local_path: Optional[str] = None
    raw_path: Optional[str] = None
    extracted_dir: Optional[str] = None
    evidence_note: str = "no_text_available"
