"""Abstract base class for all job scrapers.

Every scraper implements extract() -> transform() -> search().
The search() method is the public entry point used by the API layer.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Unified job listing representation shared across all scrapers."""

    id: str
    title: str
    company: str
    location: str
    url: str
    summary: str
    source: str
    posted_at: Optional[str] = None
    salary: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON responses."""
        return asdict(self)


class BaseScraper(ABC):
    """Interface that every job source scraper must implement."""

    source_name: str = "unknown"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    @abstractmethod
    def extract(self, query: str, location: str, page: int) -> object:
        """Fetch raw data (HTML or JSON) from the upstream source.

        Returns the raw payload on success, or None on failure.
        """

    @abstractmethod
    def transform(self, raw: object) -> List[Job]:
        """Parse the raw payload into a list of Job objects."""

    def search(
        self, query: str = "", location: str = "", page: int = 1
    ) -> List[Job]:
        """High-level entry point: extract -> transform with error handling.

        Never raises — returns an empty list and logs on failure so the API
        layer can always produce a valid response.
        """
        try:
            raw = self.extract(query, location, page)
            if raw is None:
                logger.warning("[%s] extract returned None", self.source_name)
                return []
            jobs = self.transform(raw)
            logger.info("[%s] got %d jobs for q=%r loc=%r", self.source_name, len(jobs), query, location)
            return jobs
        except Exception:
            logger.exception("[%s] scraper failed", self.source_name)
            return []
