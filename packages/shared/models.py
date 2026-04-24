from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TargetPaper:
    canonical_id: str | None
    title: str | None
    doi: str | None
    source_ids: dict[str, str] = field(default_factory=dict)
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    input_type: str = "unknown"
    resolve_status: str = "unresolved"
