from __future__ import annotations

import os
import re
from pathlib import Path
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

from apps.analyzer.config import build_llm
from packages.sentiment.models import ReferenceMatch
from packages.sentiment.reference_locator import sentence_spans, split_sentences
from packages.shared.models import TargetPaper

LATEX_CITE_PATTERN = re.compile(r"\\cite[t|p]?\{([^}]+)\}")


class ReferenceSelectionModel(BaseModel):
    matched: bool = Field(description="Whether one reference entry matches the target paper.")
    reference_index: int = Field(description="Selected reference entry index, or -1 if no match.")
    citation_marker: Optional[str] = Field(default=None, description="The body citation marker linked to that entry, such as [7] or (Smith, 2020).")
    matched_reference: Optional[str] = Field(default=None, description="Short textual description of the matched reference.")
    evidence_note: str = Field(description="Why this reference was chosen or rejected.")


class ContextSelectionModel(BaseModel):
    matched: bool = Field(description="Whether one context window clearly cites the selected target reference.")
    window_index: int = Field(description="Selected window index, or -1 if no match.")
    evidence_note: str = Field(description="Why this context was selected or rejected.")


def locate_reference_context_with_llm(
    text: str,
    target_paper: TargetPaper,
    source_type: Optional[str] = None,
    extracted_dir: Optional[str] = None,
    max_reference_entries: int = 24,
    max_candidate_windows: int = 16,
) -> ReferenceMatch:
    if not (target_paper.title or target_paper.doi or target_paper.paper_query):
        raise RuntimeError("stage5 llm locator requires target paper hints")

    if source_type == "latex" and extracted_dir:
        tex_match = locate_reference_context_from_tex_sources(
            target_paper=target_paper,
            extracted_dir=Path(extracted_dir),
        )
        if tex_match.context_text:
            return tex_match

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
        "You are matching a target paper against reference entries extracted from a citing paper. "
        "Use the title, DOI, aliases, and semantic description to decide which reference entry is the target paper. "
        "If no entry matches, return matched=false. "
        "When the source comes from TeX/LaTeX, assume the reliable path is: find the bibliography entry first, recover the citation key or marker, then use that key or marker to find body citations."
    )
    reference_block = "\n\n".join(f"[{index}] {entry}" for index, entry in enumerate(reference_entries))
    reference_result = structured_reference_llm.invoke(
        [
            {"role": "system", "content": reference_prompt},
            {
                "role": "user",
                "content": (
                    f"Target paper hints:\n{target_hints}\n\n"
                    f"Source type: {source_type or 'unknown'}\n"
                    f"Extracted dir: {extracted_dir or 'none'}\n\n"
                    f"Extraction logs:\n{extraction_logs}\n\n"
                    f"Reference entries:\n{reference_block}"
                ),
            },
        ]
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
        "You are selecting the body context that cites a target reference entry. "
        "Use the chosen reference entry and the citation marker if available. "
        "Prefer the window that actually discusses the target work rather than a neighboring citation. "
        "When the source is TeX/LaTeX, prioritize windows carrying the recovered citation key/marker and treat that as stronger evidence than loose semantic similarity."
    )
    window_block = "\n\n".join(f"[{index}] {window['text']}" for index, window in enumerate(candidate_windows))
    context_result = structured_context_llm.invoke(
        [
            {"role": "system", "content": context_prompt},
            {
                "role": "user",
                "content": (
                    f"Target paper hints:\n{target_hints}\n\n"
                    f"Source type: {source_type or 'unknown'}\n"
                    f"Extracted dir: {extracted_dir or 'none'}\n\n"
                    f"Selected reference entry:\n{selected_entry}\n\n"
                    f"Citation marker hint:\n{reference_result.citation_marker or 'none'}\n\n"
                    f"Candidate body windows:\n{window_block}"
                ),
            },
        ]
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
    match = find_bibliography_heading(text)
    if not match:
        return text, "", "reference_section=not_found"
    body_text = text[: match.start()].strip()
    reference_text = text[match.end() :].strip()
    return body_text, reference_text, "reference_section=found"


def extract_reference_entries(reference_text: str, max_entries: int = 24) -> List[str]:
    if not reference_text.strip():
        return []

    numbered = re.split(r"(?=\[\d+\])|(?=(?:^|\s)\d+\.\s)", reference_text)
    entries = [normalize_window_text(chunk) for chunk in numbered if normalize_window_text(chunk)]
    if len(entries) <= 1:
        chunks = re.split(r"(?<=\.)\s+(?=[A-Z][a-z].+?\d{4})", reference_text)
        entries = [normalize_window_text(chunk) for chunk in chunks if normalize_window_text(chunk)]
    return entries[:max_entries]


def build_candidate_windows(body_text: str, citation_marker: Optional[str], max_windows: int = 16) -> List[dict[str, int | str]]:
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
    parts = []
    if target_paper.title:
        parts.append(f"title={target_paper.title}")
    if target_paper.doi:
        parts.append(f"doi={target_paper.doi}")
    if target_paper.paper_query and target_paper.paper_query != target_paper.title:
        parts.append(f"query={target_paper.paper_query}")
    return "\n".join(parts)


def normalize_window_text(text: str) -> str:
    return " ".join(text.split())


def find_bibliography_heading(text: str) -> Optional[re.Match[str]]:
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


def locate_reference_context_from_tex_sources(target_paper: TargetPaper, extracted_dir: Path) -> ReferenceMatch:
    if not extracted_dir.exists() or not extracted_dir.is_dir():
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="tex_extracted_dir_missing",
        )

    target_doi = (target_paper.doi or "").lower()
    target_title = (target_paper.title or target_paper.paper_query or "").lower()

    bibliography_hit = find_bibliography_match(extracted_dir, target_doi=target_doi, target_title=target_title)
    if bibliography_hit is None:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="tex_bibliography_match_not_found",
        )

    citation_key, bibliography_entry, bibliography_path = bibliography_hit
    context_hit = find_body_context_for_citation_key(extracted_dir, citation_key)
    if context_hit is None:
        return ReferenceMatch(
            matched_target_reference=bibliography_entry,
            context_text=None,
            mention_span=None,
            evidence_note=f"tex_citation_key_found_but_body_context_missing:{citation_key}",
        )

    context_text, source_path = context_hit
    return ReferenceMatch(
        matched_target_reference=f"{citation_key} @ {bibliography_path.name}",
        context_text=context_text,
        mention_span=None,
        evidence_note=f"matched_by_tex_bibliography_and_cite_key:{citation_key} @ {source_path.name}",
    )


def find_bibliography_match(extracted_dir: Path, target_doi: str, target_title: str) -> Optional[tuple[str, str, Path]]:
    for path in iter_source_files(extracted_dir, suffixes={".bib", ".bbl", ".tex"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() == ".bib":
            bib_match = find_bib_entry_match(text, target_doi=target_doi, target_title=target_title)
            if bib_match:
                return bib_match[0], bib_match[1], path
        else:
            bibitem_match = find_bibitem_match(text, target_doi=target_doi, target_title=target_title)
            if bibitem_match:
                return bibitem_match[0], bibitem_match[1], path
    return None


def find_bib_entry_match(text: str, target_doi: str, target_title: str) -> Optional[tuple[str, str]]:
    entry_pattern = re.compile(r"@(?P<kind>\w+)\{(?P<key>[^,]+),(?P<body>.*?)(?=@\w+\{|$)", re.DOTALL)
    for match in entry_pattern.finditer(text):
        key = match.group("key").strip()
        body = match.group("body")
        lowered = body.lower()
        if target_doi and target_doi in lowered:
            return key, normalize_window_text(match.group(0))
        if target_title and target_title in lowered:
            return key, normalize_window_text(match.group(0))
    return None


def find_bibitem_match(text: str, target_doi: str, target_title: str) -> Optional[tuple[str, str]]:
    entry_pattern = re.compile(r"\\bibitem(?:\[[^\]]+\])?\{(?P<key>[^}]+)\}(?P<body>.*?)(?=\\bibitem|$)", re.DOTALL)
    for match in entry_pattern.finditer(text):
        key = match.group("key").strip()
        body = match.group("body")
        lowered = body.lower()
        if target_doi and target_doi in lowered:
            return key, normalize_window_text(match.group(0))
        if target_title and target_title in lowered:
            return key, normalize_window_text(match.group(0))
    return None


def find_body_context_for_citation_key(extracted_dir: Path, citation_key: str) -> Optional[tuple[str, Path]]:
    escaped_key = re.escape(citation_key)
    cite_pattern = re.compile(rf"\\cite[t|p]?\{{[^}}]*\b{escaped_key}\b[^}}]*\}}")
    for path in iter_source_files(extracted_dir, suffixes={".tex"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "\\bibitem" in text:
            # Prefer body files over bibliography-style TeX fragments when possible.
            continue
        for match in cite_pattern.finditer(text):
            context = extract_tex_context(text, match.start(), match.end())
            return normalize_window_text(mark_target_cite_in_context(context, citation_key=citation_key)), path
    # Fall back to any TeX file, including those that may mix body and bibliography.
    for path in iter_source_files(extracted_dir, suffixes={".tex"}):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in cite_pattern.finditer(text):
            context = extract_tex_context(text, match.start(), match.end())
            return normalize_window_text(mark_target_cite_in_context(context, citation_key=citation_key)), path
    return None


def extract_tex_context(text: str, start: int, end: int, window: int = 280) -> str:
    paragraph_start = find_left_boundary(text, start, patterns=[r"\n\s*\n"])
    paragraph_end = find_right_boundary(text, end, patterns=[r"\n\s*\n"])

    sentence_start = find_left_boundary(text, start, patterns=[r"(?<=[\.;])\s", r"\n"])
    sentence_end = find_right_boundary(text, end, patterns=[r"(?<=[\.;])\s", r"\n"])

    left = max(0, min(sentence_start, start - window, paragraph_start))
    right = min(len(text), max(sentence_end, end + window, paragraph_end))
    snippet = text[left:right].strip()

    # Prefer the containing paragraph if it is reasonably bounded.
    paragraph = text[paragraph_start:paragraph_end].strip()
    if paragraph and len(paragraph) <= 900:
        return paragraph

    # Otherwise prefer the sentence/statement bounded by period or semicolon.
    sentence = text[sentence_start:sentence_end].strip()
    if sentence and len(sentence) <= 700:
        return sentence

    return snippet


def find_left_boundary(text: str, index: int, patterns: List[str]) -> int:
    boundary = 0
    prefix = text[:index]
    for pattern in patterns:
        matches = list(re.finditer(pattern, prefix, re.MULTILINE))
        if matches:
            boundary = max(boundary, matches[-1].end())
    return boundary


def find_right_boundary(text: str, index: int, patterns: List[str]) -> int:
    boundary = len(text)
    suffix = text[index:]
    for pattern in patterns:
        match = re.search(pattern, suffix, re.MULTILINE)
        if match:
            boundary = min(boundary, index + match.start())
    return boundary


def iter_source_files(root: Path, suffixes: set[str]) -> List[Path]:
    paths: List[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            paths.append(path)
    paths.sort(key=lambda item: str(item))
    return paths


def evenly_spaced_indexes(total: int, max_windows: int) -> List[int]:
    if total <= max_windows:
        return list(range(total))
    if max_windows <= 1:
        return [0]

    indexes = {0, total - 1}
    step = (total - 1) / float(max_windows - 1)
    for slot in range(max_windows):
        indexes.add(int(round(slot * step)))
    return sorted(indexes)[:max_windows]


def mark_target_cite_in_context(context: str, citation_key: str) -> str:
    escaped_key = re.escape(citation_key)
    cite_pattern = re.compile(rf"(\\cite[t|p]?\{{[^}}]*\b{escaped_key}\b[^}}]*\}})")
    return cite_pattern.sub(r"**\1**", context)
