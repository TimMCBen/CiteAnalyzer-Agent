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
    evidence_note: str = Field(description="用中文简明说明选择该 label 的依据。")


def classify_sentiment(context_text: str, target_paper: TargetPaper) -> tuple[SentimentLabel, str]:
    normalized = " ".join(context_text.split())
    if len(normalized) < 24:
        return "unknown", "context_too_short_for_llm_classification"

    llm = build_llm()
    structured_llm = llm.with_structured_output(SentimentClassificationModel, method="function_calling")
    target_hint = target_paper.title or target_paper.doi or target_paper.paper_query or "unknown target"
    prompt = (
        "你正在判断一段引用上下文对目标论文的态度。"
        "如果上下文中有用双星号标出的精确目标引用，例如 **this**，必须优先以该标记为判断锚点。"
        "字段名和枚举值不要翻译；label 必须且只能使用英文枚举 positive、neutral、critical、unknown。"
        "当上下文支持、采用、基于或扩展目标工作时，使用 label=positive。"
        "当上下文指出目标工作的限制、失败、弱点，或明确与目标工作形成负面对比时，使用 label=critical。"
        "当上下文主要是背景介绍、事实列举或中性提及时，使用 label=neutral。"
        "只有当上下文证据不足以支持任何判断时，才使用 label=unknown。"
        "evidence_note 必须使用中文，简明说明判断依据；论文标题、作者名、arXiv ID 和专业术语可以保留英文原文。"
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
