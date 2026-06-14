"""Build the outbound HTTP request (URL + headers) from search criteria.

Isolating request construction means adding a new filter later (e.g. job type,
date posted) is a change in one place rather than string-fiddling in the fetch
or service code.
"""
from urllib.parse import urlencode

from config import ScraperConfig


def build_search_url(
    config: ScraperConfig,
    *,
    query: str,
    location: str,
    radius: int,
    start: int = 0,
) -> str:
    """Return the fully-qualified search URL for one results page."""
    params = {"q": query, "l": location, "radius": radius}
    if start:
        params["start"] = start
    return f"{config.base_url}?{urlencode(params)}"


def build_headers(config: ScraperConfig) -> dict:
    """Return the request headers for a scraping call."""
    return config.headers
