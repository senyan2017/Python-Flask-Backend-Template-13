"""Orchestrate a full scraping run across multiple result pages.

This is the only module that ties the other layers together: build a request,
fetch it, parse it, and accumulate results page by page.
"""
from config import DEFAULT_CONFIG, ScraperConfig
from .fetcher import fetch_page
from .parser import parse_jobs
from .request_builder import build_headers, build_search_url


def get_jobs(
    *,
    query: str = None,
    location: str = None,
    radius: int = None,
    pages: int = None,
    config: ScraperConfig = DEFAULT_CONFIG,
) -> list:
    """Return a list of job dicts for the given criteria.

    Any argument left as None falls back to the value in `config`, so callers
    only need to pass what they want to override.

    If some pages fail but at least one succeeds, the partial results are
    returned. Only when every page fails is the underlying FetchError raised,
    so a single blocked page never sinks the whole request.
    """
    query = query or config.default_query
    location = location or config.default_location
    radius = radius if radius is not None else config.default_radius
    pages = pages if pages is not None else config.default_pages

    headers = build_headers(config)
    jobs = []
    succeeded = 0
    last_error = None

    for page in range(pages):
        start = page * config.results_per_page
        url = build_search_url(
            config,
            query=query,
            location=location,
            radius=radius,
            start=start,
        )
        try:
            html = fetch_page(url, headers, config.request_timeout)
        except Exception as exc:  # FetchError; keep going to other pages
            last_error = exc
            continue

        jobs.extend(parse_jobs(html, config.selectors))
        succeeded += 1

    if succeeded == 0 and last_error is not None:
        raise last_error

    return jobs
