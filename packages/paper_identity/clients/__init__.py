"""Package exports for the clients paper identity matching module."""
from __future__ import annotations

from packages.paper_identity.clients.arxiv import ArxivMetadataClient
from packages.paper_identity.clients.openalex_work import OpenAlexWorkClient

__all__ = ["ArxivMetadataClient", "OpenAlexWorkClient"]
