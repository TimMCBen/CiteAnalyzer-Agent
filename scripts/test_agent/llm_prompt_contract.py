"""Validate that LLM prompts require Chinese evidence text."""
from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.shared.models import TargetPaper
from scripts.test_agent.stage_logging import StageLogger


class CapturingStructuredLLM:
    """Fake structured LLM that records prompts sent by prompt contract tests."""
    def __init__(self, outputs: list[SimpleNamespace]):
        self.outputs = outputs
        self.system_prompts: list[str] = []

    def with_structured_output(self, model, method: str):
        """Return the fake client while accepting LangChain-style configuration."""
        _ = model, method
        return self

    def invoke(self, messages: list[dict[str, str]]):
        """Record the system prompt and return the next queued fake response."""
        self.system_prompts.append(messages[0]["content"])
        if not self.outputs:
            raise AssertionError("fake LLM output queue exhausted")
        return self.outputs.pop(0)


def assert_classifier_prompt_requires_chinese_evidence() -> None:
    import packages.sentiment.classifier as classifier

    fake_llm = CapturingStructuredLLM(
        [
            SimpleNamespace(
                label="neutral",
                evidence_note="该引用只是把目标论文作为背景工作列出，没有正向采用或批评。",
            )
        ]
    )
    original_build_llm = classifier.build_llm
    classifier.build_llm = lambda: fake_llm
    try:
        label, evidence_note = classifier.classify_sentiment(
            "This prior work list cites **SPC** as background without evaluation.",
            TargetPaper(title="SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning"),
        )
    finally:
        classifier.build_llm = original_build_llm

    assert label == "neutral", label
    assert evidence_note.startswith("llm_sentiment:"), evidence_note
    assert "该引用只是" in evidence_note, evidence_note
    prompt = fake_llm.system_prompts[0]
    assert "label 必须且只能使用英文枚举" in prompt, prompt
    assert "evidence_note 必须使用中文" in prompt, prompt
    assert "1-2 句自然通顺" in prompt, prompt
    assert "不要包含字段名" in prompt, prompt
    assert "llm_sentiment" in prompt, prompt
    assert "原因：前缀" in prompt, prompt
    assert "作为背景、相关工作、事实列举或分类归纳" in prompt, prompt


def assert_locator_prompts_require_chinese_evidence() -> None:
    import packages.sentiment.llm_locator as llm_locator

    fake_llm = CapturingStructuredLLM(
        [
            SimpleNamespace(
                matched=True,
                reference_index=0,
                citation_marker="(Chen et al., 2025a)",
                matched_reference="Chen et al. 2025a. SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning.",
                evidence_note="参考文献 [0] 的标题与目标论文完全一致，年份和作者线索也匹配。",
            ),
            SimpleNamespace(
                matched=True,
                window_index=0,
                evidence_note="窗口 0 明确包含 Chen et al., 2025a，并把目标论文作为 prior work 讨论。",
            ),
        ]
    )
    original_build_llm = llm_locator.build_llm
    llm_locator.build_llm = lambda: fake_llm
    try:
        text = (
            "Self-play methods include SPC (Chen et al., 2025a), which studies critic evolution. "
            "This sentence gives enough body context for citation detection. "
            "Additional filler keeps the references section in the latter half of the document. "
            "Additional filler keeps the references section in the latter half of the document. "
            "Additional filler keeps the references section in the latter half of the document.\n\n"
            "References\n"
            "[0] Chen et al. 2025a. SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning."
        )
        match = llm_locator.locate_reference_context_with_llm(
            text,
            TargetPaper(title="SPC: Evolving Self-Play Critic via Adversarial Games for LLM Reasoning"),
            source_type="pdf",
        )
    finally:
        llm_locator.build_llm = original_build_llm

    assert match.evidence_note.startswith("matched_by_llm_reference_and_context:"), match.evidence_note
    assert "参考文献 [0]" in match.evidence_note, match.evidence_note
    assert "窗口 0" in match.evidence_note, match.evidence_note
    assert len(fake_llm.system_prompts) == 2, fake_llm.system_prompts
    assert "evidence_note 必须使用中文" in fake_llm.system_prompts[0], fake_llm.system_prompts[0]
    assert "evidence_note 必须使用中文" in fake_llm.system_prompts[1], fake_llm.system_prompts[1]
    assert "字段名和结构化取值不要翻译" in fake_llm.system_prompts[0], fake_llm.system_prompts[0]
    assert "字段名和结构化取值不要翻译" in fake_llm.system_prompts[1], fake_llm.system_prompts[1]


def main() -> None:
    """Run prompt-language contract assertions."""
    logger = StageLogger("llm_prompt_contract")
    logger.start()
    assert_classifier_prompt_requires_chinese_evidence()
    logger.pass_case("classifier_prompt_requires_chinese_evidence")
    assert_locator_prompts_require_chinese_evidence()
    logger.pass_case("locator_prompts_require_chinese_evidence")
    logger.done("llm prompt contract validation passed")


if __name__ == "__main__":
    main()
