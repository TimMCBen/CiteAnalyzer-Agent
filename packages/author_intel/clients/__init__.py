"""Package exports for the clients author intelligence module."""
from packages.author_intel.clients.dblp import DBLPClient
from packages.author_intel.clients.openalex import OpenAlexClient

__all__ = ["DBLPClient", "OpenAlexClient"]
