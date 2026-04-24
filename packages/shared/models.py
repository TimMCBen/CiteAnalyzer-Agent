from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TargetPaper:
    canonical_id: str | None
    title: str | None
    doi: str | None
    source_ids: dict[str, str] = field(default_factory=dict)
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    input_type: str = "unknown"
    resolve_status: str = "unresolved"

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_id": self.canonical_id,
            "title": self.title,
            "doi": self.doi,
            "source_ids": dict(self.source_ids),
            "year": self.year,
            "authors": list(self.authors),
            "input_type": self.input_type,
            "resolve_status": self.resolve_status,
        }


@dataclass
class AnalysisRequest:
    paper_input: str
    time_range: str | None = None
    report_format: str = "html"
    source_toggles: dict[str, bool] = field(default_factory=dict)
