"""Centralised defaults for the job scraper.

Anything that might change between environments or Indeed page revisions
lives here so the rest of the codebase never hard-codes the same value twice.
"""

BASE_URL = "https://www.indeed.com/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Indeed paginates in steps of 10 (start=0, start=10, start=20 …).
PAGE_STEP = 10

# How many pages to fetch when the caller does not specify.
DEFAULT_PAGE_COUNT = 3

# Maximum pages a caller may request in a single call.
MAX_PAGE_COUNT = 10

# Request timeout in seconds.
REQUEST_TIMEOUT = 10

# Default search parameters used when the client omits them.
DEFAULT_QUERY = "Software Engineer"
DEFAULT_LOCATION = "Raleigh, NC"
DEFAULT_RADIUS = 50

# CSS selectors / class names used by the parser.
# Keeping them in one place means a Indeed markup change only touches this file.
SELECTORS = {
    "job_card": "job_seen_beacon",
    "title": "h2.jobTitle a",
    "company": "span[data-testid='company-name']",
    "location": "div[data-testid='text-location']",
    "salary": "div.salary-snippet-container",
    "summary": "div.job-snippet",
}
