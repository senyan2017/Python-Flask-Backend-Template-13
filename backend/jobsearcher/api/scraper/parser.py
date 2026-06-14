"""HTML parsing and result formatting layer.

Knows how to walk a BeautifulSoup document produced by the fetcher and
extract structured job dictionaries.  If Indeed changes its markup, only
the selectors in ``config.SELECTORS`` and the helpers here need updating.
"""

from bs4 import BeautifulSoup

from config import SELECTORS


def _safe_text(element) -> str:
    """Return stripped text from an element, or '' if the element is None."""
    if element is None:
        return ""
    return element.get_text(strip=True)


def _parse_card(card) -> dict:
    """Extract a single job dictionary from one job-card element."""
    title_el = card.select_one(SELECTORS["title"])
    company_el = card.select_one(SELECTORS["company"])
    location_el = card.select_one(SELECTORS["location"])
    salary_el = card.select_one(SELECTORS["salary"])
    summary_el = card.select_one(SELECTORS["summary"])

    return {
        "title": _safe_text(title_el),
        "company": _safe_text(company_el),
        "location": _safe_text(location_el),
        "salary": _safe_text(salary_el),
        "summary": _safe_text(summary_el).replace("\n", ""),
    }


def parse_jobs(soup: BeautifulSoup) -> list[dict]:
    """Walk the page and return a list of job dictionaries."""
    cards = soup.select(f"div.{SELECTORS['job_card']}")
    jobs = [_parse_card(card) for card in cards]
    # Filter out completely empty cards (e.g. ad slots).
    return [job for job in jobs if job["title"]]
