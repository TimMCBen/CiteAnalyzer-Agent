"""Stage5 fulltext acquisition and parsing."""

from packages.sentiment.fulltext import fetch_fulltext_document, select_text_source
from packages.sentiment.models import FullTextDocument, TextSourceSelection

__all__ = [
    "fetch_fulltext_document",
    "FullTextDocument",
    "select_text_source",
    "TextSourceSelection",
]
