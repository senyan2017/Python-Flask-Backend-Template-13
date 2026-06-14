"""Exceptions raised by the scraper, so the API layer can handle failures
through a single, well-defined error type instead of catching raw library
errors scattered everywhere.
"""


class ScraperError(Exception):
    """Base class for any recoverable scraping failure."""


class FetchError(ScraperError):
    """Raised when a page could not be retrieved (network error / bad status)."""


class ParseError(ScraperError):
    """Raised when retrieved HTML could not be parsed at all."""
