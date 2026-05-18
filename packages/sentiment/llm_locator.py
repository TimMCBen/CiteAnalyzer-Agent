"""LLM-assisted target-reference and context locator for citing papers."""
from __future__ import annotations

import re
from typing import List, Optional

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

from apps.analyzer.config import build_llm, invoke_llm_with_retry
from packages.sentiment.models import ReferenceMatch
from packages.sentiment.reference_locator import sentence_spans, split_sentences
from packages.shared.models import TargetPaper


class ReferenceSelectionModel(BaseModel):
    """Validate the LLM decision that selects the target reference entry."""
    matched: bool = Field(description="Whether one reference entry matches the target paper.")
    reference_index: int = Field(description="Selected reference entry index, or -1 if no match.")
    citation_marker: Optional[str] = Field(default=None, description="The body citation marker linked to that entry, such as [7] or (Smith, 2020).")
    matched_reference: Optional[str] = Field(default=None, description="Short textual description of the matched reference.")
    evidence_note: str = Field(description="用中文说明为什么选择或拒绝该参考文献。")


class ContextSelectionModel(BaseModel):
    """Validate the LLM decision that selects a body citation window."""
    matched: bool = Field(description="Whether one context window clearly cites the selected target reference.")
    window_index: int = Field(description="Selected window index, or -1 if no match.")
    evidence_note: str = Field(description="用中文说明为什么选择或拒绝该正文窗口。")


def locate_reference_context_with_llm(
    text: str,
    target_paper: TargetPaper,
    source_type: Optional[str] = None,
    extracted_dir: Optional[str] = None,
    max_reference_entries: int = 24,
    max_candidate_windows: int = 16,
) -> ReferenceMatch:
    """Match the target paper to references and body windows using structured LLM calls."""
    if not (target_paper.title or target_paper.doi or target_paper.paper_query):
        raise RuntimeError("stage5 llm locator requires target paper hints")

    body_text, reference_text, extraction_logs = split_document_sections(text)
    reference_entries = extract_reference_entries(reference_text, max_entries=max_reference_entries)
    if not reference_entries:
        reference_entries = extract_reference_entries(text, max_entries=max_reference_entries)
    if not reference_entries:
        raise RuntimeError("stage5 llm locator could not extract any reference entries")

    llm = build_llm()
    structured_reference_llm = llm.with_structured_output(ReferenceSelectionModel, method="function_calling")
    target_hints = build_target_hints(target_paper)
    reference_prompt = (
        "你正在把目标论文与施引论文中抽取出的参考文献条目进行匹配。"
        "请根据标题、DOI、别名和语义描述判断哪一条参考文献是目标论文。"
        "字段名和结构化取值不要翻译；matched、reference_index、citation_marker、matched_reference 必须按 schema 输出。"
        "如果没有任何条目匹配目标论文，返回 matched=false。"
        "evidence_note 必须使用中文，简明说明选择或拒绝该参考文献的理由；论文标题、DOI、arXiv ID 和引用标记可保留原文。"
    )
    reference_block = "\n\n".join(f"[{index}] {entry}" for index, entry in enumerate(reference_entries))
    reference_result = invoke_llm_with_retry(
        structured_reference_llm,
        [
            {"role": "system", "content": reference_prompt},
            {
                "role": "user",
                "content": (
                    f"Target paper hints:\n{target_hints}\n\n"
                    f"Source type: {source_type or 'unknown'}\n"
                    f"Extraction logs:\n{extraction_logs}\n\n"
                    f"Reference entries:\n{reference_block}"
                ),
            },
        ],
        "阶段6参考文献匹配",
    )

    if not reference_result.matched or reference_result.reference_index < 0 or reference_result.reference_index >= len(reference_entries):
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note=f"llm_reference_not_found:{reference_result.evidence_note}",
        )

    selected_entry = reference_entries[reference_result.reference_index]
    candidate_windows = build_candidate_windows(
        body_text=body_text,
        citation_marker=reference_result.citation_marker,
        max_windows=max_candidate_windows,
    )
    if not candidate_windows:
        candidate_windows = build_candidate_windows(
            body_text=body_text,
            citation_marker=None,
            max_windows=max_candidate_windows,
        )
    if not candidate_windows:
        raise RuntimeError("stage5 llm locator could not build any candidate body windows")

    structured_context_llm = llm.with_structured_output(ContextSelectionModel, method="function_calling")
    context_prompt = (
        "你正在从候选正文窗口中选择真正引用目标参考文献的上下文。"
        "请优先使用已选参考文献和 citation marker；如果 marker 可用，它比宽泛语义相似更可靠。"
        "应选择实际讨论目标工作的窗口，不要选择只是相邻引用或主题相近但未引用目标论文的窗口。"
        "字段名和结构化取值不要翻译；matched 和 window_index 必须按 schema 输出。"
        "evidence_note 必须使用中文，简明说明为什么选择或拒绝该正文窗口；论文标题、引用标记和专业术语可保留原文。"
    )
    window_block = "\n\n".join(f"[{index}] {window['text']}" for index, window in enumerate(candidate_windows))
    context_result = invoke_llm_with_retry(
        structured_context_llm,
        [
            {"role": "system", "content": context_prompt},
            {
                "role": "user",
                "content": (
                    f"Target paper hints:\n{target_hints}\n\n"
                    f"Source type: {source_type or 'unknown'}\n"
                    f"Selected reference entry:\n{selected_entry}\n\n"
                    f"Citation marker hint:\n{reference_result.citation_marker or 'none'}\n\n"
                    f"Candidate body windows:\n{window_block}"
                ),
            },
        ],
        "阶段6引用窗口选择",
    )

    if not context_result.matched or context_result.window_index < 0 or context_result.window_index >= len(candidate_windows):
        return ReferenceMatch(
            matched_target_reference=reference_result.matched_reference or selected_entry,
            context_text=None,
            mention_span=None,
            evidence_note=f"llm_context_not_found:{context_result.evidence_note}",
        )

    selected_window = candidate_windows[context_result.window_index]
    return ReferenceMatch(
        matched_target_reference=reference_result.matched_reference or selected_entry,
        context_text=selected_window["text"],
        mention_span=(selected_window["start"], selected_window["end"]),
        evidence_note=f"matched_by_llm_reference_and_context:{reference_result.evidence_note} | {context_result.evidence_note}",
    )


def split_document_sections(text: str) -> tuple[str, str, str]:
    """Separate body text from reference text when a bibliography heading is reliable."""
    match = find_bibliography_heading(text)
    if not match:
        return text, "", "reference_section=not_found"
    body_text = text[: match.start()].strip()
    reference_text = text[match.end() :].strip()
    return body_text, reference_text, "reference_section=found"


def extract_reference_entries(reference_text: str, max_entries: int = 24) -> List[str]:
    """Split a reference section into candidate bibliography entries."""
    if not reference_text.strip():
        return []

    numbered = re.split(r"(?=\[\d+\])|(?=(?:^|\s)\d+\.\s)", reference_text)
    entries = [normalize_window_text(chunk) for chunk in numbered if normalize_window_text(chunk)]
    if len(entries) <= 1:
        chunks = re.split(r"(?<=\.)\s+(?=[A-Z][a-z].+?\d{4})", reference_text)
        entries = [normalize_window_text(chunk) for chunk in chunks if normalize_window_text(chunk)]
    return entries[:max_entries]


def build_candidate_windows(body_text: str, citation_marker: Optional[str], max_windows: int = 16) -> List[dict[str, int | str]]:
    """Build body-text windows likely to contain citations for LLM selection."""
    sentences = split_sentences(body_text)
    spans = sentence_spans(body_text)
    windows: List[dict[str, int | str]] = []

    for index, sentence in enumerate(sentences):
        sentence_text = sentence.strip()
        if not sentence_text:
            continue
        looks_like_citation = bool(re.search(r"\[\d+(?:\s*,\s*\d+)*\]|\([A-Z][^)]*\d{4}[a-z]?\)|\\cite[t|p]?\{[^}]+\}", sentence_text))
        marker_hit = citation_marker and citation_marker in sentence_text
        if not marker_hit and not looks_like_citation:
            continue
        start_sentence = max(0, index - 1)
        end_sentence = min(len(sentences), index + 2)
        start = spans[start_sentence][0]
        end = spans[end_sentence - 1][1]
        windows.append(
            {
                "start": start,
                "end": end,
                "text": " ".join(sentences[start_sentence:end_sentence]).strip(),
            }
        )

    if windows:
        return dedupe_windows(windows)[:max_windows]

    # Fall back to evenly sampled windows across the body.
    fallback_windows: List[dict[str, int | str]] = []
    for index in range(len(sentences)):
        start_sentence = index
        end_sentence = min(len(sentences), index + 2)
        start = spans[start_sentence][0]
        end = spans[end_sentence - 1][1]
        fallback_windows.append(
            {
                "start": start,
                "end": end,
                "text": " ".join(sentences[start_sentence:end_sentence]).strip(),
            }
        )
    deduped = dedupe_windows(fallback_windows)
    if len(deduped) <= max_windows:
        return deduped
    sampled_indexes = evenly_spaced_indexes(len(deduped), max_windows=max_windows)
    return [deduped[index] for index in sampled_indexes]


def dedupe_windows(windows: List[dict[str, int | str]]) -> List[dict[str, int | str]]:
    """Remove duplicate context windows while preserving their first occurrence."""
    unique: List[dict[str, int | str]] = []
    seen: set[str] = set()
    for window in windows:
        key = str(window["text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(window)
    return unique


def build_target_hints(target_paper: TargetPaper) -> str:
    """Format target-paper identifiers for reference-matching prompts."""
    parts = []
    if target_paper.title:
        parts.append(f"title={target_paper.title}")
    if target_paper.doi:
        parts.append(f"doi={target_paper.doi}")
    if target_paper.paper_query and target_paper.paper_query != target_paper.title:
        parts.append(f"query={target_paper.paper_query}")
    return "\n".join(parts)


def normalize_window_text(text: str) -> str:
    """Collapse whitespace in reference entries and candidate windows."""
    return " ".join(text.split())


def find_bibliography_heading(text: str) -> Optional[re.Match[str]]:
    """Find a likely References or Bibliography heading near the document end."""
    heading_pattern = re.compile(r"(?im)^(references|bibliography)\s*$")
    matches = list(heading_pattern.finditer(text))
    if not matches:
        return None

    total_len = max(1, len(text))
    candidates: List[tuple[int, re.Match[str]]] = []
    for match in matches:
        start = match.start()
        relative_pos = start / total_len
        if relative_pos < 0.5:
            continue
        following_text = text[match.end() : match.end() + 4000]
        score = score_bibliography_region(following_text)
        if score <= 0:
            continue
        position_bonus = int(relative_pos * 10)
        candidates.append((score + position_bonus, match))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1].start()))
    return candidates[-1][1]


def score_bibliography_region(text: str) -> int:
    """Score text after a heading for signals that it is a bibliography."""
    score = 0
    if re.search(r"@(?:article|inproceedings|book|misc)\{", text, re.IGNORECASE):
        score += 5
    if re.search(r"\\bibitem(?:\[[^\]]+\])?\{", text):
        score += 5
    if len(re.findall(r"(?m)^\s*\[\d+\]", text)) >= 2:
        score += 4
    if len(re.findall(r"\b(?:19|20)\d{2}\b", text)) >= 4:
        score += 2
    if len(re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.IGNORECASE)) >= 1:
        score += 2
    if len(re.findall(r"\bProceedings\b|\bJournal\b|\bConference\b", text, re.IGNORECASE)) >= 2:
        score += 1
    return score


def evenly_spaced_indexes(total: int, max_windows: int) -> List[int]:
    """Sample candidate-window indexes across long documents for prompt coverage."""
    if total <= max_windows:
        return list(range(total))
    if max_windows <= 1:
        return [0]

    indexes = {0, total - 1}
    step = (total - 1) / float(max_windows - 1)
    for slot in range(max_windows):
        indexes.add(int(round(slot * step)))
    return sorted(indexes)[:max_windows]
