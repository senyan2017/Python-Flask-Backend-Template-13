"""Perform the HTTP fetch and nothing else.

This layer only knows how to turn a URL into raw HTML, translating any transport
failure into a FetchError so callers never deal with `requests` internals.
"""
import requests

from .exceptions import FetchError


def fetch_page(url: str, headers: dict, timeout: int) -> str:
    """Fetch a single page and return its HTML text."""
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"Request to {url} failed: {exc}") from exc

    if response.status_code != 200:
        raise FetchError(
            f"Unexpected status {response.status_code} from {url}"
        )

    return response.text
