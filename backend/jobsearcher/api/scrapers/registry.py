"""Scraper registry — aggregates results from multiple sources.

The API layer talks to the registry, not to individual scrapers.
Adding a new source is just:

    1. Create scrapers/mysource.py extending BaseScraper
    2. Register it here:  registry.register(MySourceScraper())
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)


class ScraperRegistry:
    """Manages multiple scraper backends and aggregates their results."""

    def __init__(self) -> None:
        self._scrapers: Dict[str, BaseScraper] = {}

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers[scraper.source_name] = scraper
        logger.info("Registered scraper: %s", scraper.source_name)

    def unregister(self, name: str) -> None:
        self._scrapers.pop(name, None)

    @property
    def sources(self) -> List[str]:
        return list(self._scrapers.keys())

    def search(
        self,
        query: str = "",
        location: str = "",
        page: int = 1,
        page_size: int = 20,
        source: Optional[str] = None,
    ) -> dict:
        """Run search across one or all scrapers and return a unified response.

        Returns a dict with:
          - jobs: list of job dicts
          - total: total number of jobs found
          - page / page_size / total_pages: pagination metadata
          - query / location: echoed back for the frontend
          - sources: which sources were queried
          - errors: per-source error info (empty if everything succeeded)
        """
        if source and source in self._scrapers:
            scrapers_to_run = {source: self._scrapers[source]}
        else:
            scrapers_to_run = dict(self._scrapers)

        all_jobs: List[Job] = []
        errors: Dict[str, str] = {}

        for name, scraper in scrapers_to_run.items():
            try:
                jobs = scraper.search(query, location, page)
                all_jobs.extend(jobs)
            except Exception as exc:
                logger.exception("[%s] unexpected error in registry", name)
                errors[name] = str(exc)

        # Client-side pagination over aggregated results
        total = len(all_jobs)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        page_jobs = all_jobs[start:end]

        return {
            "jobs": [j.to_dict() for j in page_jobs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "query": query,
            "location": location,
            "sources": list(scrapers_to_run.keys()),
            "errors": errors,
        }
