"""Tests for the /retrieveJobs API endpoint and the indeedScraper module.

Covers:
  - Successful query with jobs returned
  - Empty result set (no jobs found)
  - Missing / invalid query parameters
  - Scraper timeout
  - Scraper HTTP error from upstream
  - Generic scraper / internal error
  - Consistent response shape across all scenarios
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure the api package directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from api import app  # noqa: E402
from indeedScraper import (  # noqa: E402
    ScraperError,
    ScraperTimeoutError,
    ScraperHttpError,
    ScraperParseError,
    _parse_single_card,
    _safe_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


SAMPLE_JOBS = [
    {
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "Raleigh, NC",
        "salary": "$120,000 - $150,000 a year",
        "summary": "Build great software.",
    },
    {
        "title": "Data Analyst",
        "company": "Globex",
        "location": "Durham, NC",
        "salary": "",
        "summary": "Analyze data.",
    },
]


# ---------------------------------------------------------------------------
# Helper: assert unified response shape
# ---------------------------------------------------------------------------

def assert_shape(resp_json, expect_success):
    """Every response must have these top-level keys."""
    assert "success" in resp_json
    assert "message" in resp_json
    assert "data" in resp_json
    assert "error" in resp_json
    assert resp_json["success"] is expect_success
    assert isinstance(resp_json["data"], list)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestSuccessScenarios:
    @patch("api.getList", return_value=SAMPLE_JOBS)
    def test_normal_query_returns_200(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=engineer&location=Raleigh%2C+NC")
        assert resp.status_code == 200
        body = resp.get_json()
        assert_shape(body, expect_success=True)
        assert len(body["data"]) == 2
        assert body["data"][0]["title"] == "Software Engineer"
        assert body["error"] is None
        mock_scraper.assert_called_once_with(
            keyword="engineer", location="Raleigh, NC", radius=25
        )

    @patch("api.getList", return_value=[])
    def test_empty_result_returns_200_with_empty_list(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=unicorn+dev&location=Atlantis")
        assert resp.status_code == 200
        body = resp.get_json()
        assert_shape(body, expect_success=True)
        assert body["data"] == []
        assert "0 job(s)" in body["message"]

    @patch("api.getList", return_value=SAMPLE_JOBS[:1])
    def test_custom_radius_passed_through(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC&radius=50")
        assert resp.status_code == 200
        mock_scraper.assert_called_once_with(
            keyword="dev", location="NYC", radius=50
        )


class TestValidationErrors:
    def test_missing_keyword_returns_400(self, client):
        resp = client.get("/retrieveJobs?location=NYC")
        assert resp.status_code == 400
        body = resp.get_json()
        assert_shape(body, expect_success=False)
        assert body["error"]["code"] == "INVALID_PARAMS"
        assert "keyword" in body["message"].lower()

    def test_empty_keyword_returns_400(self, client):
        resp = client.get("/retrieveJobs?keyword=&location=NYC")
        assert resp.status_code == 400
        body = resp.get_json()
        assert_shape(body, expect_success=False)

    def test_missing_location_returns_400(self, client):
        resp = client.get("/retrieveJobs?keyword=engineer")
        assert resp.status_code == 400
        body = resp.get_json()
        assert_shape(body, expect_success=False)
        assert "location" in body["message"].lower()

    def test_whitespace_only_params_returns_400(self, client):
        resp = client.get("/retrieveJobs?keyword=%20%20&location=%20")
        assert resp.status_code == 400

    def test_no_params_at_all_returns_400(self, client):
        resp = client.get("/retrieveJobs")
        assert resp.status_code == 400

    def test_radius_not_a_number_returns_400(self, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC&radius=abc")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["error"]["code"] == "INVALID_PARAMS"

    def test_radius_out_of_range_returns_400(self, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC&radius=999")
        assert resp.status_code == 400

    def test_negative_radius_returns_400(self, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC&radius=-5")
        assert resp.status_code == 400

    def test_oversized_keyword_returns_400(self, client):
        resp = client.get(f"/retrieveJobs?keyword={'x' * 201}&location=NYC")
        assert resp.status_code == 400


class TestScraperErrors:
    @patch("api.getList", side_effect=ScraperTimeoutError("timed out after 10s"))
    def test_timeout_returns_504(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC")
        assert resp.status_code == 504
        body = resp.get_json()
        assert_shape(body, expect_success=False)
        assert body["error"]["code"] == "SCRAPER_TIMEOUT"

    @patch("api.getList", side_effect=ScraperHttpError(403, "Forbidden"))
    def test_upstream_http_error_returns_502(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC")
        assert resp.status_code == 502
        body = resp.get_json()
        assert_shape(body, expect_success=False)
        assert body["error"]["code"] == "SCRAPER_ERROR"

    @patch("api.getList", side_effect=ScraperError("something broke"))
    def test_generic_scraper_error_returns_502(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC")
        assert resp.status_code == 502
        body = resp.get_json()
        assert_shape(body, expect_success=False)

    @patch("api.getList", side_effect=RuntimeError("totally unexpected"))
    def test_unexpected_exception_returns_500(self, mock_scraper, client):
        resp = client.get("/retrieveJobs?keyword=dev&location=NYC")
        assert resp.status_code == 500
        body = resp.get_json()
        assert_shape(body, expect_success=False)
        assert body["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Scraper unit tests (field-level resilience)
# ---------------------------------------------------------------------------

class TestScraperFieldResilience:
    """Verify that _parse_single_card handles missing fields gracefully."""

    def _make_soup_card(self, html_fragment):
        from bs4 import BeautifulSoup
        full = f'<html><body><div class="jobsearch-SerpJobCard">{html_fragment}</div></body></html>'
        soup = BeautifulSoup(full, "html.parser")
        return soup.find("div", class_="jobsearch-SerpJobCard")

    def test_full_card(self):
        card = self._make_soup_card(
            '<a>Software Engineer</a>'
            '<span class="company">Acme</span>'
            '<span class="location">NYC</span>'
            '<span class="salaryText">$100k</span>'
            '<div class="summary">Great job\nReally great</div>'
        )
        job = _parse_single_card(card)
        assert job["title"] == "Software Engineer"
        assert job["company"] == "Acme"
        assert job["location"] == "NYC"
        assert job["salary"] == "$100k"
        assert "\n" not in job["summary"]

    def test_missing_company_defaults_to_unknown(self):
        card = self._make_soup_card(
            '<a>Dev</a>'
            '<span class="location">NYC</span>'
        )
        job = _parse_single_card(card)
        assert job["title"] == "Dev"
        assert job["company"] == "Unknown"

    def test_missing_location_defaults_to_na(self):
        card = self._make_soup_card(
            '<a>Dev</a>'
            '<span class="company">Corp</span>'
        )
        job = _parse_single_card(card)
        assert job["location"] == "N/A"

    def test_missing_salary_defaults_to_empty(self):
        card = self._make_soup_card(
            '<a>Dev</a>'
            '<span class="company">Corp</span>'
            '<span class="location">NYC</span>'
        )
        job = _parse_single_card(card)
        assert job["salary"] == ""

    def test_no_title_returns_none(self):
        card = self._make_soup_card(
            '<span class="company">Corp</span>'
            '<span class="location">NYC</span>'
        )
        job = _parse_single_card(card)
        assert job is None

    def test_safe_text_none_tag(self):
        assert _safe_text(None) is None


class TestScraperExceptionHierarchy:
    def test_timeout_is_scraper_error(self):
        assert issubclass(ScraperTimeoutError, ScraperError)

    def test_http_error_is_scraper_error(self):
        assert issubclass(ScraperHttpError, ScraperError)

    def test_parse_error_is_scraper_error(self):
        assert issubclass(ScraperParseError, ScraperError)

    def test_http_error_stores_status(self):
        exc = ScraperHttpError(429)
        assert exc.status_code == 429
        assert "429" in str(exc)
