"""Backward-compatible facade for the old indeedScraper module.

The original workshop code imported `getList` from this file.
This shim keeps that import working while delegating to the new
scraper layer under ``scrapers/``.

New code should import directly from ``scrapers`` instead.
"""

from __future__ import annotations

from scrapers import IndeedScraper, RemotiveScraper, ScraperRegistry

_scraper_registry = ScraperRegistry()
_scraper_registry.register(RemotiveScraper())
_scraper_registry.register(IndeedScraper())


def getList(query: str = "", location: str = "", page: int = 1) -> list[dict]:
    """Return a flat list of job dicts from all registered scrapers.

    Kept for backward compatibility with the original workshop template.
    Prefer calling the API endpoint directly for new code.
    """
    result = _scraper_registry.search(query=query, location=location, page=page)
    return result["jobs"]


# ---- Legacy extract / transform stubs (for anyone importing them) --------
_indeed = IndeedScraper()


def extract(query: str = "", location: str = "", page: int = 1):
    return _indeed.extract(query, location, page)


def transform(raw):
    return _indeed.transform(raw)
