"""Indeed.com HTML scraper.

Indeed aggressively blocks automated requests (Cloudflare, CAPTCHAs, rate
limits), so this scraper is best-effort.  When it fails the API layer will
simply fall back to other sources — it will NOT crash the whole response.

The CSS selectors target the card structure Indeed used as of mid-2024.
If Indeed changes their markup, update the selectors in transform() and
the _SEL constants at the top of this file.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)

BASE_URL = "https://www.indeed.com"

# Selectors — update these when Indeed changes their markup
_SEL_CARD = "div.job_seen_beacon"
_SEL_TITLE = "h2.jobTitle a"
_SEL_COMPANY = "span[data-testid='company-name']"
_SEL_LOCATION = "div[data-testid='text-location']"
_SEL_SUMMARY = "div.job-snippet"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class IndeedScraper(BaseScraper):
    source_name = "indeed"

    def extract(self, query: str, location: str, page: int) -> Optional[BeautifulSoup]:
        params = {
            "q": query or "",
            "l": location or "",
            "start": str((page - 1) * 10),
        }
        url = f"{BASE_URL}/jobs"
        try:
            resp = requests.get(
                url, params=params, headers=_HEADERS, timeout=self.timeout
            )
            if resp.status_code != 200:
                logger.warning(
                    "[indeed] non-200 status %s — likely blocked", resp.status_code
                )
                return None
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as exc:
            logger.error("[indeed] HTTP error: %s", exc)
            return None

    def transform(self, raw: BeautifulSoup) -> List[Job]:
        cards = raw.select(_SEL_CARD)
        if not cards:
            # Fallback: try the older card class
            cards = raw.select("div.tapItem")
        jobs: List[Job] = []
        for idx, card in enumerate(cards):
            title_el = card.select_one(_SEL_TITLE)
            company_el = card.select_one(_SEL_COMPANY)
            location_el = card.select_one(_SEL_LOCATION)
            summary_el = card.select_one(_SEL_SUMMARY)

            if not title_el:
                continue

            href = title_el.get("href", "")
            job_url = urljoin(BASE_URL, href) if href else ""

            # Indeed sometimes prepends "new" to the title text
            title_text = title_el.get_text(strip=True)
            title_text = re.sub(r"^new\s*", "", title_text, flags=re.IGNORECASE)

            jobs.append(
                Job(
                    id=f"indeed-{idx}-{hash(job_url) & 0xFFFFFFFF:08x}",
                    title=title_text,
                    company=company_el.get_text(strip=True) if company_el else "",
                    location=location_el.get_text(strip=True) if location_el else "",
                    url=job_url,
                    summary=summary_el.get_text(strip=True) if summary_el else "",
                    source=self.source_name,
                )
            )
        return jobs
