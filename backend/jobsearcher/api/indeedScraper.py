import requests
from bs4 import BeautifulSoup

## This file is the Indeed.com scraper for the Backend PackHacks workshop. This file is set
## up in a extract, transform, and return format, which should be followed for other similar
## scrappers if you are wanting to scrape other sites.
## We import requests and BeautifulSoup from pip install beautifulsoup4 to do the scrapping.
## @author Travis Walter - 3/16/2021

INDEED_BASE_URL = "https://www.indeed.com/jobs"
REQUEST_TIMEOUT = 10  # seconds
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class ScraperError(Exception):
    """Base exception for scraper-related errors."""
    pass


class ScraperTimeoutError(ScraperError):
    """Raised when the request to Indeed times out."""
    pass


class ScraperHttpError(ScraperError):
    """Raised when Indeed returns a non-200 HTTP status."""
    def __init__(self, status_code, message=None):
        self.status_code = status_code
        super().__init__(message or f"Indeed returned HTTP {status_code}")


class ScraperParseError(ScraperError):
    """Raised when the HTML cannot be parsed at all."""
    pass


def extract(page_num, keyword, location, radius=25):
    """Fetch a single page of Indeed search results.

    Args:
        page_num: Pagination offset (0, 10, 20, ...).
        keyword: Job search keyword (e.g. "Software Engineer").
        location: Location string (e.g. "Raleigh, NC").
        radius: Search radius in miles.

    Returns:
        A BeautifulSoup instance of the parsed page.

    Raises:
        ScraperTimeoutError: If the request exceeds REQUEST_TIMEOUT seconds.
        ScraperHttpError: If Indeed returns a non-200 status code.
        ScraperParseError: If the response body cannot be parsed.
    """
    params = {
        "q": keyword,
        "l": location,
        "radius": radius,
        "start": page_num,
    }
    try:
        r = requests.get(
            INDEED_BASE_URL,
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ScraperTimeoutError(
            f"Request to Indeed timed out after {REQUEST_TIMEOUT}s"
        ) from exc
    except requests.ConnectionError as exc:
        raise ScraperHttpError(0, "Unable to connect to Indeed") from exc
    except requests.RequestException as exc:
        raise ScraperError(f"Unexpected request error: {exc}") from exc

    if r.status_code != 200:
        raise ScraperHttpError(r.status_code)

    try:
        soup = BeautifulSoup(r.content, "html.parser")
    except Exception as exc:
        raise ScraperParseError(f"Failed to parse HTML: {exc}") from exc

    return soup


def transform(job_list, soup):
    """Parse job cards from a BeautifulSoup page and append them to job_list.

    Fields that are missing on individual cards are filled with sensible
    defaults so that one incomplete card does not invalidate the whole batch.

    Args:
        job_list: Mutable list to which parsed job dicts are appended.
        soup: BeautifulSoup instance of a single Indeed results page.

    Returns:
        The same job_list reference, with new entries appended.
    """
    # Indeed changed its card class over time; try both selectors.
    cards = soup.find_all("div", class_="jobsearch-SerpJobCard")
    if not cards:
        cards = soup.find_all("div", class_="cardOutline")
    if not cards:
        # Fallback: try the newer tapItem wrapper
        cards = soup.find_all("div", class_="tapItem")

    for item in cards:
        job = _parse_single_card(item)
        if job is not None:
            job_list.append(job)

    return job_list


def _parse_single_card(item):
    """Extract fields from a single job card, returning None on total failure."""
    title = _safe_text(item.find("a")) or _safe_text(
        item.find("h2", class_="jobTitle")
    )
    if not title:
        # A card without a title is not useful — skip it.
        return None

    company = (
        _safe_text(item.find("span", class_="company"))
        or _safe_text(item.find("span", class_="companyName"))
        or "Unknown"
    )

    location = (
        _safe_text(item.find("span", class_="location"))
        or _safe_text(item.find("div", class_="companyLocation"))
        or "N/A"
    )

    try:
        salary = (
            _safe_text(item.find("span", class_="salaryText"))
            or _safe_text(item.find("div", class_="salary-snippet-container"))
            or ""
        )
    except Exception:
        salary = ""

    try:
        summary = (
            _safe_text(item.find("div", class_="summary"))
            or _safe_text(item.find("div", class_="job-snippet"))
            or ""
        )
        summary = summary.replace("\n", "")
    except Exception:
        summary = ""

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "summary": summary,
    }


def _safe_text(tag):
    """Return stripped text from a BeautifulSoup tag, or None if absent."""
    if tag is None:
        return None
    try:
        text = tag.get_text(strip=True)
        return text if text else None
    except Exception:
        return None


def getList(keyword, location, radius=25, max_pages=3):
    """Scrape Indeed for jobs matching *keyword* near *location*.

    Args:
        keyword: Search query string (must be non-empty).
        location: Location string (must be non-empty).
        radius: Search radius in miles.
        max_pages: Number of result pages to scrape (each page ~15 jobs).

    Returns:
        A list of job dictionaries.  May be empty if no jobs matched.

    Raises:
        ScraperTimeoutError: If any page request times out.
        ScraperHttpError: If any page returns a non-200 status.
        ScraperParseError: If any page cannot be parsed.
        ScraperError: For other unexpected scraper failures.
    """
    job_list = []
    for page_num in range(0, max_pages * 10, 10):
        soup = extract(page_num, keyword, location, radius)
        transform(job_list, soup)
    return job_list
