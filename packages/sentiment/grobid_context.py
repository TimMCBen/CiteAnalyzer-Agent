"""Grobid context helpers for citation sentiment analysis."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from packages.sentiment.grobid_client import process_fulltext_document
from packages.sentiment.models import ReferenceMatch
from packages.shared.models import TargetPaper

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def locate_reference_context_from_grobid_pdf(
    pdf_path: Path,
    target_paper: TargetPaper,
    output_xml_path: Path | None = None,
) -> ReferenceMatch:
    """Locate reference context from GROBID PDF for citation sentiment analysis."""
    tei_path = process_fulltext_document(pdf_path, output_xml_path=output_xml_path)
    return locate_reference_context_from_grobid_tei(tei_path=tei_path, target_paper=target_paper)


def locate_reference_context_from_grobid_tei(tei_path: Path, target_paper: TargetPaper) -> ReferenceMatch:
    """Locate reference context from GROBID tei for citation sentiment analysis."""
    root = ET.parse(tei_path).getroot()
    bibl = find_target_bibl_struct(root, target_paper=target_paper)
    if bibl is None:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="grobid_biblStruct_not_found",
        )

    bibl_id = bibl.attrib.get("{http://www.w3.org/XML/1998/namespace}id")
    if not bibl_id:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="grobid_biblStruct_missing_id",
        )

    contexts = extract_contexts_for_bibl_id(root, bibl_id=bibl_id)
    if not contexts:
        return ReferenceMatch(
            matched_target_reference=f"#{bibl_id}",
            context_text=None,
            mention_span=None,
            evidence_note=f"grobid_bibr_context_not_found:{bibl_id}",
        )

    return ReferenceMatch(
        matched_target_reference=f"#{bibl_id}",
        context_text=contexts[0],
        mention_span=None,
        evidence_note=f"matched_by_grobid_biblStruct_and_bibr:{bibl_id} @ {tei_path.name}",
    )


def find_target_bibl_struct(root: ET.Element, target_paper: TargetPaper) -> Optional[ET.Element]:
    """Find the GROBID bibliography entry matching the target paper for citation sentiment analysis."""
    target_doi = (target_paper.doi or "").strip().lower()
    target_title = normalize_ws(target_paper.title or target_paper.paper_query or "").lower()

    for bibl in root.findall(".//tei:listBibl/tei:biblStruct", TEI_NS):
        doi_el = bibl.find(".//tei:idno[@type='DOI']", TEI_NS)
        title_el = bibl.find(".//tei:title", TEI_NS)
        doi = (doi_el.text or "").strip().lower() if doi_el is not None and doi_el.text else ""
        title = normalize_ws("".join(title_el.itertext()) if title_el is not None else "").lower()
        if target_doi and doi == target_doi:
            return bibl
        if target_title and title == target_title:
            return bibl
    return None


def extract_contexts_for_bibl_id(root: ET.Element, bibl_id: str) -> list[str]:
    """Extract contexts for bibl id for citation sentiment analysis."""
    target_ref = f"#{bibl_id}"
    contexts: list[str] = []
    for paragraph in root.findall(".//tei:p", TEI_NS):
        refs = paragraph.findall(".//tei:ref[@type='bibr']", TEI_NS)
        if any(ref.attrib.get("target") == target_ref for ref in refs):
            contexts.append(serialize_paragraph_with_target_markup(paragraph, target_ref=target_ref))
    return contexts


def normalize_ws(text: str) -> str:
    """Normalize ws for citation sentiment analysis."""
    return " ".join(text.split())


def serialize_paragraph_with_target_markup(paragraph: ET.Element, target_ref: str) -> str:
    """Serialize GROBID paragraphs while preserving target citation markers for citation sentiment analysis."""
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)

        for child in list(node):
            if child.tag.endswith("ref") and child.attrib.get("type") == "bibr":
                ref_text = "".join(child.itertext())
                if child.attrib.get("target") == target_ref:
                    parts.append(f"**{ref_text}**")
                else:
                    parts.append(ref_text)
            else:
                walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(paragraph)
    return normalize_ws("".join(parts))
