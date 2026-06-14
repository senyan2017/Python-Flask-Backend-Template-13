"""Public surface of the scraper package.

The API layer should import from here only - the internal split between request
building, fetching, parsing, and orchestration is an implementation detail.
"""
from .exceptions import FetchError, ParseError, ScraperError
from .service import get_jobs

__all__ = ["get_jobs", "ScraperError", "FetchError", "ParseError"]
