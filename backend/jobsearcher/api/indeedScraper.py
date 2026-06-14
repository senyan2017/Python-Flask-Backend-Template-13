"""Indeed.com job scraper.

This fills in the workshop's original ``indeedScraper.py`` shell with a real,
working scraper built on ``requests`` + ``BeautifulSoup``. It follows the
extract / transform shape from the original template, but is wrapped in a
``BaseScraper`` subclass so the Flask layer can treat every site the same way.

Note on Indeed: Indeed runs aggressive anti-bot protection and frequently
serves a CAPTCHA / "verify you are human" wall to automated clients. When that
happens this scraper raises :class:`ScraperBlockedError` so the API can return a
clean "blocked" response instead of crashing. Use ``source=remoteok`` (see
``remoteokScraper.py``) for a source that returns real data reliably, which is
handy for verifying the end-to-end pipeline locally.
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import scrapers
from scrapers import (
    BaseScraper,
    JobPosting,
    ScraperBlockedError,
    ScraperError,
    ScrapeResult,
)

# Markers that indicate Indeed served a bot wall rather than real results.
_BLOCK_MARKERS = (
    "captcha",
    "px-captcha",
    "hcaptcha",
    "cloudflare",
    "verifying you are human",
    "are you a human",
    "additional verification required",
    "//www.google.com/recaptcha",
)

# Selectors are listed most-current first. Indeed has reorganised its markup
# several times; trying several keeps the scraper working a bit longer and makes
# it obvious where to add a new selector when the layout changes again.
_CARD_SELECTORS = (
    ("div", {"class": "job_seen_beacon"}),
    ("div", {"class": "cardOutline"}),
    ("a", {"class": "tapItem"}),
    ("div", {"class": "jobsearch-SerpJobCard"}),  # legacy (original template)
)


@scrapers.register("indeed")
class IndeedScraper(BaseScraper):
    base_url = "https://www.indeed.com"
    search_path = "/jobs"
    page_size = 10  # Indeed paginates via ?start= in steps of 10

    # -- public API --------------------------------------------------------
    def search(
        self,
        query: str,
        location: str = "",
        *,
        page: int = 1,
        limit: int = 25,
    ) -> ScrapeResult:
        start = max(page - 1, 0) * self.page_size
        params = {"q": query or "", "l": location or "", "start": start}

        resp = self._get(self.base_url + self.search_path, params=params)

        if resp.status_code in (403, 429):
            raise ScraperBlockedError(
                f"Indeed returned HTTP {resp.status_code} (rate-limited or "
                "blocked the request)."
            )
        if resp.status_code >= 400:
            raise ScraperError(f"Indeed returned HTTP {resp.status_code}.")

        soup = BeautifulSoup(resp.content, "html.parser")
        cards = self._find_cards(soup)

        if not cards:
            # Distinguish a bot wall from a legitimately empty result set.
            if self._looks_blocked(resp.text):
                raise ScraperBlockedError(
                    "Indeed served a verification/CAPTCHA page instead of "
                    "results."
                )
            return ScrapeResult(jobs=[], total=0)

        jobs: List[JobPosting] = []
        for card in cards:
            job = self._parse_card(card)
            if job is not None:
                jobs.append(job)
            if len(jobs) >= limit:
                break

        total = self._extract_total(soup, fallback=len(jobs))
        return ScrapeResult(jobs=jobs, total=total)

    # -- extract -----------------------------------------------------------
    def _find_cards(self, soup: BeautifulSoup) -> list:
        for tag, attrs in _CARD_SELECTORS:
            cards = soup.find_all(tag, class_=attrs.get("class"))
            if cards:
                return cards
        return []

    @staticmethod
    def _looks_blocked(html: str) -> bool:
        lowered = html.lower()
        return any(marker in lowered for marker in _BLOCK_MARKERS)

    # -- transform ---------------------------------------------------------
    def _parse_card(self, card) -> Optional[JobPosting]:
        title = self._first_text(
            card,
            [
                ("h2", {"class": "jobTitle"}),
                ("a", {"class": "jcs-JobTitle"}),
                ("span", {"attrs": {"title": True}}),
            ],
        )
        # The very first anchor usually carries the title as a last resort.
        if not title:
            anchor = card.find("a")
            title = anchor.get_text(strip=True) if anchor else ""
        if not title:
            return None  # not a real job card, skip it

        company = self._first_text(
            card,
            [
                ("span", {"attrs": {"data-testid": "company-name"}}),
                ("span", {"class": "companyName"}),
                ("span", {"class": "company"}),  # legacy
            ],
        )
        location = self._first_text(
            card,
            [
                ("div", {"attrs": {"data-testid": "text-location"}}),
                ("div", {"class": "companyLocation"}),
                ("span", {"class": "location"}),  # legacy
            ],
        )
        summary = self._first_text(
            card,
            [
                ("div", {"class": "job-snippet"}),
                ("div", {"class": "summary"}),  # legacy
            ],
        )
        summary = re.sub(r"\s*\n\s*", " ", summary).strip()

        salary = self._first_text(
            card,
            [
                ("div", {"class": "salary-snippet-container"}),
                ("div", {"class": "metadata salary-snippet-container"}),
                ("span", {"class": "salaryText"}),  # legacy
            ],
        )

        return JobPosting(
            title=title,
            company=company,
            location=location,
            url=self._extract_url(card),
            summary=summary,
            salary=salary,
            source=self.source_name,
        )

    def _extract_url(self, card) -> str:
        anchor = (
            card.find("a", class_="jcs-JobTitle")
            or (card.find("h2", class_="jobTitle") or card).find("a")
            or (card if card.name == "a" else None)
        )
        href = anchor.get("href") if anchor else None
        return urljoin(self.base_url, href) if href else ""

    @staticmethod
    def _extract_total(soup: BeautifulSoup, *, fallback: int) -> int:
        node = soup.find("div", class_="jobsearch-JobCountAndSortPane-jobCount")
        if node is None:
            node = soup.find(attrs={"data-testid": "searchCountPages"})
        if node is not None:
            match = re.search(r"([\d,]+)", node.get_text())
            if match:
                return int(match.group(1).replace(",", ""))
        return fallback

    # -- small helpers -----------------------------------------------------
    @staticmethod
    def _first_text(card, selectors) -> str:
        """Return stripped text from the first selector that matches."""
        for tag, opts in selectors:
            if "attrs" in opts:
                node = card.find(tag, attrs=opts["attrs"])
            else:
                node = card.find(tag, class_=opts.get("class"))
            if node is not None:
                text = node.get_text(strip=True)
                if text:
                    return text
        return ""


# ---------------------------------------------------------------------------
# Backwards-compatible helper
# ---------------------------------------------------------------------------
def getList(
    query: str = "Software Engineer",
    location: str = "Raleigh, NC",
    *,
    limit: int = 25,
) -> List[dict]:
    """Original template entry point, kept so existing code / the frontend
    workshop keep working. Returns a plain list of job dicts.

    New code should prefer ``IndeedScraper().search(...)`` (or the
    ``/retrieveJobs`` endpoint), which also reports totals and query echo.
    """
    result = IndeedScraper().search(query, location, limit=limit)
    return [job.to_dict() for job in result.jobs]
