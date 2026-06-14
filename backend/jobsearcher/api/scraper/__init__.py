"""Public interface for the scraper package.

Callers outside this package should only ever use ``get_jobs``.
"""

from config import (
    DEFAULT_LOCATION,
    DEFAULT_PAGE_COUNT,
    DEFAULT_QUERY,
    DEFAULT_RADIUS,
    MAX_PAGE_COUNT,
    PAGE_STEP,
)
from scraper.fetcher import fetch_page
from scraper.parser import parse_jobs


def get_jobs(
    query: str = DEFAULT_QUERY,
    location: str = DEFAULT_LOCATION,
    radius: int = DEFAULT_RADIUS,
    page_count: int = DEFAULT_PAGE_COUNT,
) -> list[dict]:
    """Fetch and parse Indeed job listings.

    Parameters
    ----------
    query : str
        Job search term (e.g. ``"Software Engineer"``).
    location : str
        Location filter (e.g. ``"Raleigh, NC"``).
    radius : int
        Search radius in miles.
    page_count : int
        How many result pages to crawl (clamped to ``MAX_PAGE_COUNT``).

    Returns
    -------
    list[dict]
        One dictionary per job listing.
    """
    page_count = max(1, min(page_count, MAX_PAGE_COUNT))
    jobs: list[dict] = []

    for start in range(0, page_count * PAGE_STEP, PAGE_STEP):
        soup = fetch_page(query, location, radius, start)
        jobs.extend(parse_jobs(soup))

    return jobs
