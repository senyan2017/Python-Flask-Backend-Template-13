"""Centralized configuration for the job scraper.

Everything that is likely to change over time - the source URL, default search
criteria, pagination, request headers, and the HTML selectors - lives here so
that adjusting a selector or adding a new default never means hunting for magic
strings across the whole project.
"""
from collections import namedtuple
from dataclasses import dataclass, field

# A single CSS-like target: an HTML tag plus an optional class name.
# Keeping selectors here (instead of inline in the parser) means switching to a
# new source site or reacting to markup changes is a one-file edit.
Selector = namedtuple("Selector", ["tag", "cls"])


@dataclass(frozen=True)
class Selectors:
    """HTML selectors used to pull fields out of a single job card."""

    job_card: Selector = Selector("div", "jobsearch-SerpJobCard")
    title: Selector = Selector("a", None)
    company: Selector = Selector("span", "company")
    salary: Selector = Selector("span", "salaryText")
    summary: Selector = Selector("div", "summary")


@dataclass(frozen=True)
class ScraperConfig:
    """All tunables for a scraping run, with sensible defaults."""

    base_url: str = "https://www.indeed.com/jobs"
    default_query: str = "Software Engineer"
    default_location: str = "Raleigh, NC"
    default_radius: int = 50

    # Indeed paginates in steps of 10 via the `start` query param.
    results_per_page: int = 10
    default_pages: int = 3

    request_timeout: int = 10
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    selectors: Selectors = field(default_factory=Selectors)

    @property
    def headers(self) -> dict:
        return {"User-Agent": self.user_agent}


# Shared default instance used when a caller does not supply its own config.
DEFAULT_CONFIG = ScraperConfig()
