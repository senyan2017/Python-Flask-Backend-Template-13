"""Shared scraper framework for the Job Searcher backend.

This module is the small "framework" that the Flask layer (``api.py``) talks to.
It defines:

* ``JobPosting`` / ``ScrapeResult`` -- the data the frontend actually renders.
* A small exception hierarchy so the API can tell *why* a scrape failed.
* ``BaseScraper`` -- the contract every site scraper implements.
* A tiny registry (``register`` / ``get_scraper`` / ``available_sources``).

Adding a new job site is intentionally cheap (see requirement: "swap sites
without a full rewrite"):

1. Create ``somethingScraper.py`` with a ``BaseScraper`` subclass.
2. Decorate the class with ``@register("something")``.
3. Add the module name to ``_BUILTIN_MODULES`` below.

``api.py`` never changes when you add a source.
"""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import requests

# A normal desktop User-Agent. Many sites reject the default ``python-requests``
# UA outright, so we send a realistic one. Override per scraper if needed.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class ScraperError(Exception):
    """A *recoverable* scrape failure.

    The API layer catches this and returns a clean, structured response instead
    of a raw HTTP 500. ``error_type`` is surfaced to the caller so the frontend
    can distinguish "the site blocked us" from "the site changed its layout".
    """

    error_type = "scrape_failed"


class ScraperNetworkError(ScraperError):
    """The request never completed (timeout, DNS failure, connection reset)."""

    error_type = "network_error"


class ScraperBlockedError(ScraperError):
    """The site answered but refused us (HTTP 403/429, CAPTCHA, bot wall)."""

    error_type = "blocked"


class ScraperParseError(ScraperError):
    """The response arrived but its shape was not what we expected."""

    error_type = "parse_error"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class JobPosting:
    """A single job listing -- only fields the frontend is expected to show."""

    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    summary: str = ""
    salary: str = ""
    source: str = ""
    posted: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScrapeResult:
    """What a scraper hands back to the API layer.

    ``jobs`` is the current page. ``total`` is the best-effort count of *all*
    matches (used by the frontend for pagination). Scrapers that cannot know the
    true total should set it to ``len(jobs)``.
    """

    jobs: List[JobPosting]
    total: int = 0

    def __post_init__(self) -> None:
        if self.total < len(self.jobs):
            self.total = len(self.jobs)


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------
class BaseScraper(ABC):
    """Contract for a single job site.

    Subclasses implement :meth:`search`. They should return an empty
    ``ScrapeResult`` when the site genuinely has no matches, and raise a
    :class:`ScraperError` subclass when something actually went wrong.
    """

    source_name = "base"
    base_url = ""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or requests.Session()
        self.user_agent = user_agent
        self.timeout = timeout

    @abstractmethod
    def search(
        self,
        query: str,
        location: str = "",
        *,
        page: int = 1,
        limit: int = 25,
    ) -> ScrapeResult:
        """Return jobs matching ``query``/``location`` for the given page."""

    # -- shared helpers ----------------------------------------------------
    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        }
        if extra:
            headers.update(extra)
        return headers

    def _get(self, url: str, *, params: Optional[dict] = None,
             headers: Optional[dict] = None) -> requests.Response:
        """GET ``url`` and translate transport failures into ScraperError.

        Status-code handling (403 vs 200-but-empty etc.) is left to the caller,
        because what counts as "blocked" vs "no results" differs per site.
        """
        try:
            return self.session.get(
                url,
                params=params,
                headers=self._headers(headers),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ScraperNetworkError(
                f"Could not reach {url}: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: dict = {}

# Built-in scraper modules. Each imports this module and registers itself via
# the ``@register`` decorator. Add new source modules here -- this is the only
# central list you touch when introducing a site.
_BUILTIN_MODULES = ("indeedScraper", "remoteokScraper")
_builtins_loaded = False


def register(name: str):
    """Class decorator that records a scraper under ``name`` (case-insensitive)."""

    def decorator(cls):
        key = name.strip().lower()
        cls.source_name = key
        _REGISTRY[key] = cls
        return cls

    return decorator


def _ensure_builtins() -> None:
    """Import the built-in scraper modules once so they self-register.

    Done lazily (not at import time) to avoid a circular import: the scraper
    modules import *this* module for ``BaseScraper`` and ``register``.
    """
    global _builtins_loaded
    if _builtins_loaded:
        return
    _builtins_loaded = True
    for module_name in _BUILTIN_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception:
            # A broken/optional source must not take down the whole registry.
            continue


def get_scraper(name: str) -> Optional[BaseScraper]:
    """Return an instance of the scraper registered as ``name``, or ``None``."""
    _ensure_builtins()
    cls = _REGISTRY.get((name or "").strip().lower())
    return cls() if cls is not None else None


def available_sources() -> List[str]:
    """Names of all registered sources, sorted."""
    _ensure_builtins()
    return sorted(_REGISTRY)
