"""HTTP fetching layer.

Builds the request URL from search parameters, performs the GET request,
and returns a BeautifulSoup document ready for parsing.  This module has
*no* knowledge of job-specific HTML structure — it only deals with
network I/O.
"""

import requests
from bs4 import BeautifulSoup

from config import BASE_URL, HEADERS, PAGE_STEP, REQUEST_TIMEOUT


def build_url(query: str, location: str, radius: int, start: int) -> str:
    """Return a fully-formed Indeed search URL."""
    params = {
        "q": query,
        "l": location,
        "radius": radius,
        "start": start,
    }
    query_string = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{BASE_URL}?{query_string}"


def fetch_page(query: str, location: str, radius: int, start: int = 0) -> BeautifulSoup:
    """Download one page of Indeed search results and return parsed HTML."""
    url = build_url(query, location, radius, start)
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")
