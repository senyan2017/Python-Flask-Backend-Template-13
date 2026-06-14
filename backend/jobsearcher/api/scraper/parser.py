"""Turn raw HTML into a list of job dictionaries.

All knowledge of the page structure lives behind the selectors passed in, so the
parser itself stays agnostic to the specific markup of any one site.
"""
from bs4 import BeautifulSoup

from config import Selector, Selectors
from .exceptions import ParseError


def parse_jobs(html: str, selectors: Selectors) -> list:
    """Parse every job card found in `html` into a list of dicts."""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # pragma: no cover - defensive
        raise ParseError(f"Could not parse HTML: {exc}") from exc

    card_sel = selectors.job_card
    cards = soup.find_all(card_sel.tag, class_=card_sel.cls)
    return [_parse_card(card, selectors) for card in cards]


def _parse_card(card, selectors: Selectors) -> dict:
    """Extract the fields of interest from a single job card."""
    return {
        "title": _text(card, selectors.title),
        "company": _text(card, selectors.company),
        "salary": _text(card, selectors.salary),
        "summary": _text(card, selectors.summary).replace("\n", ""),
    }


def _text(card, selector: Selector) -> str:
    """Return stripped text for a selector, or '' when it is absent.

    Optional fields (such as salary, which employers may omit) simply come back
    empty instead of raising, keeping the parser tolerant of missing data.
    """
    if selector.cls:
        element = card.find(selector.tag, class_=selector.cls)
    else:
        element = card.find(selector.tag)
    return element.text.strip() if element else ""
