from __future__ import annotations

from typing import List, Optional, Tuple

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
from packages.sentiment.models import ReferenceMatch
from packages.sentiment.reference_locator import sentence_spans, split_sentences
from packages.shared.models import TargetPaper


class ReferenceLocatorModel(BaseModel):
    matched: bool = Field(description="Whether the text window refers to the target paper.")
    window_index: int = Field(description="The selected candidate window index, or -1 if no match exists.")
    matched_reference: Optional[str] = Field(default=None, description="Short note about what kind of reference was matched.")
    evidence_note: str = Field(description="A concise reason for the decision.")


def locate_reference_context_with_llm(
    text: str,
    target_paper: TargetPaper,
    max_windows: int = 8,
) -> ReferenceMatch:
    if not (target_paper.title or target_paper.doi or target_paper.paper_query):
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="llm_reference_match_skipped_missing_target_hints",
        )

    candidate_windows = build_candidate_windows(text, max_windows=max_windows)
    if not candidate_windows:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="llm_reference_match_skipped_no_candidate_windows",
        )

    llm = build_llm()
    structured_llm = llm.with_structured_output(ReferenceLocatorModel, method="function_calling")

    window_block = "\n\n".join(f"[{index}] {window['text']}" for index, window in enumerate(candidate_windows))
    target_hint_parts = []
    if target_paper.title:
        target_hint_parts.append(f"title={target_paper.title}")
    if target_paper.doi:
        target_hint_parts.append(f"doi={target_paper.doi}")
    if target_paper.paper_query and target_paper.paper_query != target_paper.title:
        target_hint_parts.append(f"query={target_paper.paper_query}")
    target_hints = "; ".join(target_hint_parts)

    prompt = (
        "You are locating whether a citing-paper text window refers to a target paper. "
        "The reference may be indirect: method nickname, concept description, paraphrase, or discussion of the same contribution. "
        "Return matched=false if none of the candidate windows clearly refers to the target paper. "
        "Only select a window when the evidence is specific enough to trust for downstream sentiment analysis."
    )

    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Target paper hints: {target_hints}\n\n"
                    f"Candidate windows:\n{window_block}\n\n"
                    "Choose the single best window index or -1 if none match."
                ),
            },
        ]
    )

    if not result.matched:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note=f"llm_no_match:{result.evidence_note}",
        )

    if result.window_index < 0 or result.window_index >= len(candidate_windows):
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="llm_invalid_window_index",
        )

    selected = candidate_windows[result.window_index]
    return ReferenceMatch(
        matched_target_reference=result.matched_reference or "llm:semantic_reference",
        context_text=selected["text"],
        mention_span=(selected["start"], selected["end"]),
        evidence_note=f"matched_by_llm:{result.evidence_note}",
    )


def build_candidate_windows(text: str, max_windows: int = 8) -> List[dict[str, int | str]]:
    spans = sentence_spans(text)
    sentences = split_sentences(text)
    windows: List[dict[str, int | str]] = []
    for index in range(len(sentences)):
        start_sentence = index
        end_sentence = min(len(sentences), index + 2)
        start = spans[start_sentence][0]
        end = spans[end_sentence - 1][1]
        window_text = " ".join(sentences[start_sentence:end_sentence]).strip()
        if window_text:
            windows.append({"start": start, "end": end, "text": window_text})

    if len(windows) <= max_windows:
        return windows

    selected_indexes = evenly_spaced_indexes(len(windows), max_windows=max_windows)
    return [windows[index] for index in selected_indexes]


def evenly_spaced_indexes(total: int, max_windows: int) -> List[int]:
    if total <= max_windows:
        return list(range(total))

    indexes = {0, total - 1}
    if max_windows == 1:
        return [0]

    step = (total - 1) / float(max_windows - 1)
    for slot in range(max_windows):
        indexes.add(int(round(slot * step)))
    return sorted(indexes)[:max_windows]
