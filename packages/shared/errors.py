"""Errors helpers for shared analyzer contracts."""
class InvalidAnalysisRequestError(ValueError):
    """Raised when a natural-language request is not a citation-analysis request."""
