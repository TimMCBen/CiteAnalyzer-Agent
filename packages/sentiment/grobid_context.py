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
    tei_path = process_fulltext_document(pdf_path, output_xml_path=output_xml_path)
    return locate_reference_context_from_grobid_tei(tei_path=tei_path, target_paper=target_paper)


def locate_reference_context_from_grobid_tei(tei_path: Path, target_paper: TargetPaper) -> ReferenceMatch:
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
    target_ref = f"#{bibl_id}"
    contexts: list[str] = []
    for paragraph in root.findall(".//tei:p", TEI_NS):
        refs = paragraph.findall(".//tei:ref[@type='bibr']", TEI_NS)
        if any(ref.attrib.get("target") == target_ref for ref in refs):
            contexts.append(normalize_ws("".join(paragraph.itertext())))
    return contexts


def normalize_ws(text: str) -> str:
    return " ".join(text.split())
