"""Remotive.com public job API scraper.

Endpoint: https://remotive.com/api/remote-jobs
Docs: https://github.com/remotive-com/remote-jobs-api

Free, no API key required, returns JSON. This is the most reliable source
in this project — use it as the default / primary scraper.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import requests

from scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveScraper(BaseScraper):
    source_name = "remotive"

    def extract(self, query: str, location: str, page: int) -> Optional[dict]:
        params = {}
        if query:
            params["search"] = query
        if location:
            params["location"] = location
        # Remotive API doesn't support server-side pagination, but we still
        # send the params so filtering happens server-side.
        try:
            resp = requests.get(API_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("[remotive] HTTP error: %s", exc)
            return None

    def transform(self, raw: dict) -> List[Job]:
        jobs_payload = raw.get("jobs", [])
        results: List[Job] = []
        for item in jobs_payload:
            results.append(
                Job(
                    id=str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Remote"),
                    url=item.get("url", ""),
                    summary=self._strip_html(item.get("description", ""))[:500],
                    source=self.source_name,
                    posted_at=item.get("publication_date"),
                    salary=item.get("salary") or None,
                    tags=item.get("tags", []),
                )
            )
        return results

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from the description without pulling in bs4."""
        import re

        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
