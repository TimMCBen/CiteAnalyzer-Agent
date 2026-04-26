from __future__ import annotations

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, **kwargs):  # type: ignore
        if "default_factory" in kwargs:
            return kwargs["default_factory"]()
        return default

from apps.analyzer.config import build_llm
from packages.sentiment.models import SentimentLabel
from packages.shared.models import TargetPaper


class SentimentClassificationModel(BaseModel):
    label: SentimentLabel = Field(description="positive, neutral, critical, or unknown")
    evidence_note: str = Field(description="A concise justification for the label.")


def classify_sentiment(context_text: str, target_paper: TargetPaper) -> tuple[SentimentLabel, str]:
    normalized = " ".join(context_text.split())
    if len(normalized) < 24:
        return "unknown", "context_too_short_for_llm_classification"

    llm = build_llm()
    structured_llm = llm.with_structured_output(SentimentClassificationModel, method="function_calling")
    target_hint = target_paper.title or target_paper.doi or target_paper.paper_query or "unknown target"
    prompt = (
        "You are classifying a citation context toward a target paper. "
        "The exact target citation mention inside the context is wrapped with double asterisks like **this** when available. "
        "Use the wrapped citation as the primary anchor for deciding what the surrounding context says about the target paper. "
        "Use label=positive when the context supports, builds on, adopts, or extends the target work. "
        "Use label=critical when the context points out limitations, failures, weaknesses, or contrasts against the target work. "
        "Use label=neutral when the context is mainly background or factual mention. "
        "Use label=unknown only when the context is too weak to justify a label."
    )
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Target paper hint: {target_hint}\n\nCitation context:\n{normalized}",
            },
        ]
    )
    return result.label, f"llm_sentiment:{result.evidence_note}"
