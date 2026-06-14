import requests
from bs4 import BeautifulSoup

## This file is the Indeed.com scraper for the Backend PackHacks workshop. It follows the
## original extract -> transform -> return design, but hardens every stage so that the Flask
## endpoint can tell apart "request timed out", "site returned something bad", and "request
## worked but found zero jobs", instead of collapsing them into a single opaque failure.
## Missing fields on a single card no longer throw away the whole page of results.

## Network / scraping configuration.
BASE_URL = "https://www.indeed.com/jobs"
DEFAULT_TIMEOUT = 10  # seconds before a request is considered timed out
DEFAULT_PAGES = 1     # number of result pages to fetch (10 listings per page)
MIN_RADIUS = 0
MAX_RADIUS = 100

## A realistic User-Agent is required or Indeed will reject the request outright.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

## Indeed has changed its markup repeatedly over the years. We try the known card containers
## in order and use the first one that yields results, so a markup tweak degrades gracefully
## instead of returning nothing.
CARD_CLASSES = ["job_seen_beacon", "jobsearch-SerpJobCard", "tapItem", "cardOutline"]


## ---------------------------------------------------------------------------
## Exception hierarchy
##
## Every scraper failure is a ScraperError, but callers can catch the specific
## subclasses to distinguish the failure mode and map it to the right HTTP status.
## ---------------------------------------------------------------------------
class ScraperError(Exception):
    """Base class for all scraper failures."""


class ScraperTimeoutError(ScraperError):
    """The request to the target site exceeded the allotted timeout."""


class ScraperHTTPError(ScraperError):
    """The target site was reachable but returned an abnormal response.

    ``status_code`` holds the upstream HTTP status when one is available
    (it is ``None`` for connection-level failures).
    """

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class ScraperParseError(ScraperError):
    """The response was received but could not be parsed as expected."""


## ---------------------------------------------------------------------------
## Parsing helpers
## ---------------------------------------------------------------------------
def safe_text(tag, default=""):
    """Return the stripped text of a BeautifulSoup tag, or ``default`` if the
    tag is missing or empty. This is the core of field resilience: a missing
    sub-element yields a default instead of raising ``AttributeError`` and
    discarding the entire card."""
    if tag is None:
        return default
    text = tag.get_text(strip=True)
    return text if text else default


def parse_card(item):
    """Parse a single job card into a dictionary.

    Returns ``None`` when the card has no usable title (the one field we treat
    as mandatory). Every other field falls back to a sensible default so that a
    listing missing its company or location is still kept rather than dropped.
    """
    title = (
        safe_text(item.find("h2", class_="jobTitle"))
        or safe_text(item.find("a", class_="jcs-JobTitle"))
        or safe_text(item.find("span", attrs={"title": True}))
    )
    if not title:
        return None

    company = safe_text(item.find("span", class_="companyName")) or "Unknown"
    location = safe_text(item.find("div", class_="companyLocation")) or "N/A"
    salary = (
        safe_text(item.find("div", class_="salary-snippet-container"))
        or safe_text(item.find("div", class_="salary-snippet"))
        or safe_text(item.find("span", class_="salaryText"))
    )
    summary = (
        safe_text(item.find("div", class_="job-snippet"))
        or safe_text(item.find("div", class_="summary"))
    ).replace("\n", " ").strip()

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "summary": summary,
    }


## ---------------------------------------------------------------------------
## Extract -> Transform -> getList
## ---------------------------------------------------------------------------
def extract(query, location, radius=50, start=0, timeout=DEFAULT_TIMEOUT):
    """Fetch one page of Indeed results and return a parsed BeautifulSoup tree.

    Raises:
        ScraperTimeoutError: the request timed out.
        ScraperHTTPError: a connection error or a non-200 response.
        ScraperParseError: the response could not be parsed.
    """
    params = {"q": query, "l": location, "radius": radius, "start": start}
    try:
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise ScraperTimeoutError(
            "Request to Indeed timed out after {}s.".format(timeout)
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ScraperHTTPError("Could not reach Indeed: {}".format(exc)) from exc

    if response.status_code != 200:
        raise ScraperHTTPError(
            "Indeed returned HTTP {}.".format(response.status_code),
            status_code=response.status_code,
        )

    try:
        return BeautifulSoup(response.content, "html.parser")
    except Exception as exc:  # pragma: no cover - parser errors are rare
        raise ScraperParseError("Could not parse Indeed response: {}".format(exc)) from exc


def transform(job_list, soup):
    """Pull job cards out of ``soup`` and append parsed dictionaries to
    ``job_list``. A single malformed card is skipped rather than aborting the
    whole batch, so partial pages still yield the listings that did parse."""
    cards = []
    for css_class in CARD_CLASSES:
        found = soup.find_all("div", class_=css_class)
        if found:
            cards = found
            break

    for item in cards:
        try:
            job = parse_card(item)
        except Exception:
            # Defensive: never let one unexpected card structure discard the page.
            continue
        if job is not None:
            job_list.append(job)

    return job_list


def getList(query, location, radius=50, pages=DEFAULT_PAGES, timeout=DEFAULT_TIMEOUT):
    """Front-facing scraper entry point used by the Flask endpoint.

    Returns a (possibly empty) list of job dictionaries. An empty list means the
    request succeeded but matched no listings -- that is a normal result, not an
    error, and is intentionally distinct from the exceptions raised on failure.
    """
    job_list = []
    for page in range(pages):
        soup = extract(query, location, radius=radius, start=page * 10, timeout=timeout)
        transform(job_list, soup)
    return job_list
