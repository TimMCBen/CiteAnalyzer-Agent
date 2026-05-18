"""Translate report target titles for Chinese-facing report headers."""
from __future__ import annotations

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, **kwargs):  # type: ignore
        return default


class TitleTranslationModel(BaseModel):
    """Validate the structured Chinese title returned by the LLM."""
    title_zh: str = Field(description="论文标题的中文翻译。")


def translate_title_to_chinese(title: str) -> str | None:
    """Translate an English paper title into Chinese with the configured LLM."""
    clean_title = title.strip()
    if not clean_title:
        return None

    from apps.analyzer.config import build_llm, invoke_llm_with_retry

    structured_llm = build_llm().with_structured_output(TitleTranslationModel, method="function_calling")
    result = invoke_llm_with_retry(
        structured_llm,
        [
            {
                "role": "system",
                "content": (
                    "你正在为中文论文被引分析报告翻译论文标题。"
                    "只输出忠实、简洁的中文标题；保留 SPC、LLM、MoRA、arXiv 等专有缩写。"
                    "不要添加解释、括号注释或额外评价。"
                ),
            },
            {"role": "user", "content": clean_title},
        ],
        "阶段7标题中文翻译",
    )
    translated = str(result.title_zh or "").strip()
    return translated or None
