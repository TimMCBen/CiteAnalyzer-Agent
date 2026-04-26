from __future__ import annotations

import re
from typing import List, Optional, Tuple

from packages.sentiment.models import ReferenceMatch
from packages.shared.models import TargetPaper


NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def locate_reference_context(text: str, target_paper: TargetPaper, window_sentences: int = 1) -> ReferenceMatch:
    normalized_text = normalize_for_matching(text)
    doi = (target_paper.doi or "").lower()
    title = target_paper.title or target_paper.paper_query or ""

    if doi:
        index = normalized_text.find(normalize_for_matching(doi))
        if index >= 0:
            return build_reference_match(
                text=text,
                anchor_index=index,
                matched_target_reference=f"doi:{doi}",
                evidence_note="matched_by_doi",
                window_sentences=window_sentences,
            )

    sentence_match = match_sentence_by_title(text=text, title=title, window_sentences=window_sentences)
    if sentence_match is not None:
        return sentence_match

    return ReferenceMatch(
        matched_target_reference=None,
        context_text=None,
        mention_span=None,
        evidence_note="target_reference_not_found",
    )


def match_sentence_by_title(text: str, title: str, window_sentences: int = 1) -> Optional[ReferenceMatch]:
    title_tokens = significant_tokens(title)
    if len(title_tokens) < 3:
        return None

    sentences = split_sentences(text)
    best_index = -1
    best_score = 0
    for index, sentence in enumerate(sentences):
        sentence_tokens = set(significant_tokens(sentence))
        overlap = sum(1 for token in title_tokens if token in sentence_tokens)
        if overlap > best_score:
            best_index = index
            best_score = overlap

    if best_index < 0:
        return None

    threshold = max(3, min(5, len(title_tokens) // 2))
    if best_score < threshold:
        return None

    start = max(0, best_index - window_sentences)
    end = min(len(sentences), best_index + window_sentences + 1)
    context = " ".join(sentence.strip() for sentence in sentences[start:end] if sentence.strip())
    anchor_sentence = sentences[best_index]
    anchor_start = text.find(anchor_sentence)
    anchor_end = anchor_start + len(anchor_sentence) if anchor_start >= 0 else -1
    mention_span = (anchor_start, anchor_end) if anchor_start >= 0 else None
    return ReferenceMatch(
        matched_target_reference=f"title:{title.strip()}",
        context_text=context or None,
        mention_span=mention_span,
        evidence_note="matched_by_title_overlap",
    )


def build_reference_match(
    text: str,
    anchor_index: int,
    matched_target_reference: str,
    evidence_note: str,
    window_sentences: int = 1,
) -> ReferenceMatch:
    spans = sentence_spans(text)
    sentence_index = 0
    for index, (start, end) in enumerate(spans):
        if start <= anchor_index <= end:
            sentence_index = index
            break

    start_index = max(0, sentence_index - window_sentences)
    end_index = min(len(spans), sentence_index + window_sentences + 1)
    context = " ".join(text[start:end].strip() for start, end in spans[start_index:end_index] if text[start:end].strip())
    mention_span = spans[sentence_index] if spans else None
    return ReferenceMatch(
        matched_target_reference=matched_target_reference,
        context_text=context or None,
        mention_span=mention_span,
        evidence_note=evidence_note,
    )


def split_sentences(text: str) -> List[str]:
    return [segment for segment in re.split(r"(?<=[.!?])\s+|\n+", text) if segment.strip()]


def sentence_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for sentence in split_sentences(text):
        start = text.find(sentence, cursor)
        if start < 0:
            continue
        end = start + len(sentence)
        spans.append((start, end))
        cursor = end
    return spans


def significant_tokens(text: str) -> List[str]:
    tokens = [token for token in normalize_for_matching(text).split() if len(token) >= 3]
    stopwords = {
        "that",
        "with",
        "from",
        "this",
        "their",
        "have",
        "using",
        "into",
        "toward",
        "paper",
        "study",
        "based",
        "analysis",
    }
    return [token for token in tokens if token not in stopwords]


def normalize_for_matching(text: str) -> str:
    lowered = text.lower()
    return NON_ALNUM_PATTERN.sub(" ", lowered).strip()
