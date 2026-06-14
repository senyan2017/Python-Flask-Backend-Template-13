"""RemoteOK job scraper.

RemoteOK exposes a public JSON feed at ``https://remoteok.com/api`` that returns
real, current remote-job listings. Because it is plain JSON (no anti-bot wall),
it is the easiest way to verify the whole backend end-to-end locally:

    curl 'http://127.0.0.1:5000/retrieveJobs?source=remoteok&q=python'

It also demonstrates the point of the ``BaseScraper`` design: a completely
different site (JSON instead of HTML) plugs in without the Flask layer changing.
"""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

import scrapers
from scrapers import (
    BaseScraper,
    JobPosting,
    ScraperBlockedError,
    ScraperError,
    ScraperParseError,
    ScrapeResult,
)

_SUMMARY_MAX = 320


@scrapers.register("remoteok")
class RemoteOkScraper(BaseScraper):
    base_url = "https://remoteok.com"
    api_url = "https://remoteok.com/api"

    def search(
        self,
        query: str,
        location: str = "",
        *,
        page: int = 1,
        limit: int = 25,
    ) -> ScrapeResult:
        resp = self._get(self.api_url, headers={"Accept": "application/json"})

        if resp.status_code in (403, 429):
            raise ScraperBlockedError(
                f"RemoteOK returned HTTP {resp.status_code}."
            )
        if resp.status_code >= 400:
            raise ScraperError(f"RemoteOK returned HTTP {resp.status_code}.")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise ScraperParseError(
                "RemoteOK response was not valid JSON."
            ) from exc
        if not isinstance(payload, list):
            raise ScraperParseError(
                "RemoteOK response was not the expected JSON array."
            )

        # The first element is a legal/metadata object, not a job; skip anything
        # without an id so a layout tweak can't smuggle junk into the results.
        rows = [r for r in payload if isinstance(r, dict) and r.get("id")]

        terms = [t for t in (query or "").lower().split() if t]
        loc_filter = (location or "").strip().lower()

        matched: List[JobPosting] = []
        for row in rows:
            if not self._matches(row, terms, loc_filter):
                continue
            matched.append(self._to_job(row))

        total = len(matched)
        start = (max(page, 1) - 1) * limit
        page_jobs = matched[start:start + limit]
        return ScrapeResult(jobs=page_jobs, total=total)

    # -- filtering ---------------------------------------------------------
    @staticmethod
    def _matches(row: dict, terms: List[str], loc_filter: str) -> bool:
        if terms:
            haystack = " ".join(
                [
                    str(row.get("position", "")),
                    str(row.get("company", "")),
                    " ".join(row.get("tags", []) or []),
                ]
            ).lower()
            if not all(term in haystack for term in terms):
                return False
        if loc_filter:
            if loc_filter not in str(row.get("location", "")).lower():
                return False
        return True

    # -- mapping -----------------------------------------------------------
    def _to_job(self, row: dict) -> JobPosting:
        return JobPosting(
            title=str(row.get("position", "")).strip(),
            company=str(row.get("company", "")).strip(),
            location=str(row.get("location", "")).strip() or "Remote",
            url=self._absolute_url(row.get("url", "")),
            summary=self._clean_summary(row.get("description", "")),
            salary=self._format_salary(row),
            source=self.source_name,
            posted=str(row.get("date", "")),
            tags=list(row.get("tags", []) or []),
        )

    def _absolute_url(self, url: str) -> str:
        url = str(url or "")
        if url.startswith("http"):
            return url
        if url:
            return self.base_url + ("" if url.startswith("/") else "/") + url
        return ""

    @staticmethod
    def _clean_summary(description: str) -> str:
        text = BeautifulSoup(str(description or ""), "html.parser").get_text(" ")
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > _SUMMARY_MAX:
            text = text[:_SUMMARY_MAX].rstrip() + "..."
        return text

    @staticmethod
    def _format_salary(row: dict) -> str:
        low, high = row.get("salary_min"), row.get("salary_max")
        if low and high:
            return f"${int(low):,} - ${int(high):,}"
        if low:
            return f"From ${int(low):,}"
        if high:
            return f"Up to ${int(high):,}"
        return ""
