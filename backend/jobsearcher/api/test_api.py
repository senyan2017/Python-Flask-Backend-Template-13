import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

import api
from indeedScraper import (
    safe_text,
    parse_card,
    ScraperError,
    ScraperTimeoutError,
    ScraperHTTPError,
    ScraperParseError,
)

ENDPOINT = "/retrieveJobs"


def make_card(title=True, company=True, location=True, salary=True, summary=True):
    """Build a single Indeed-style job card element with optional fields, so we
    can exercise the parser's resilience to missing data."""
    parts = ['<div class="job_seen_beacon">']
    if title:
        parts.append('<h2 class="jobTitle"><a>Software Engineer</a></h2>')
    if company:
        parts.append('<span class="companyName">Acme Corp</span>')
    if location:
        parts.append('<div class="companyLocation">Raleigh, NC</div>')
    if salary:
        parts.append('<div class="salary-snippet">$120,000 a year</div>')
    if summary:
        parts.append('<div class="job-snippet">Build great software.</div>')
    parts.append("</div>")
    soup = BeautifulSoup("".join(parts), "html.parser")
    return soup.find("div", class_="job_seen_beacon")


class BaseApiTest(unittest.TestCase):
    def setUp(self):
        api.app.config["TESTING"] = True
        self.client = api.app.test_client()

    def get(self, **params):
        return self.client.get(ENDPOINT, query_string=params)


class TestSuccessScenarios(BaseApiTest):
    @patch("api.getList")
    def test_normal_query_returns_200(self, mock_get):
        mock_get.return_value = [
            {"title": "Dev", "company": "Acme", "location": "Raleigh, NC", "salary": "", "summary": "x"},
            {"title": "Eng", "company": "Globex", "location": "Cary, NC", "salary": "$1", "summary": "y"},
        ]
        resp = self.get(q="python", l="Raleigh, NC")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["status"], "success")
        self.assertIsNone(body["error"])
        self.assertIsInstance(body["data"], list)
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["data"]), 2)

    @patch("api.getList")
    def test_empty_result_returns_200_with_empty_list(self, mock_get):
        mock_get.return_value = []
        resp = self.get(q="nonexistentjob", l="Nowhere")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"], [])
        self.assertEqual(body["count"], 0)
        self.assertIsNone(body["error"])

    @patch("api.getList")
    def test_custom_radius_passed_through(self, mock_get):
        mock_get.return_value = []
        resp = self.get(q="python", l="Raleigh, NC", radius=25)
        self.assertEqual(resp.status_code, 200)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs.get("radius"), 25)


class TestValidationErrors(BaseApiTest):
    def assert_bad_request(self, resp):
        body = resp.get_json()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["data"], [])
        self.assertEqual(body["error"]["type"], "invalid_request")

    @patch("api.getList")
    def test_missing_keyword_returns_400(self, mock_get):
        self.assert_bad_request(self.get(l="Raleigh, NC"))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_empty_keyword_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="", l="Raleigh, NC"))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_whitespace_only_params_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="   ", l="   "))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_missing_location_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="python"))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_oversized_keyword_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="a" * 101, l="Raleigh, NC"))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_no_params_at_all_returns_400(self, mock_get):
        self.assert_bad_request(self.client.get(ENDPOINT))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_radius_not_a_number_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="python", l="Raleigh, NC", radius="abc"))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_negative_radius_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="python", l="Raleigh, NC", radius=-5))
        mock_get.assert_not_called()

    @patch("api.getList")
    def test_radius_out_of_range_returns_400(self, mock_get):
        self.assert_bad_request(self.get(q="python", l="Raleigh, NC", radius=99999))
        mock_get.assert_not_called()


class TestScraperErrors(BaseApiTest):
    @patch("api.getList")
    def test_timeout_returns_504(self, mock_get):
        mock_get.side_effect = ScraperTimeoutError("timed out")
        resp = self.get(q="python", l="Raleigh, NC")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 504)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["type"], "timeout")
        self.assertEqual(body["data"], [])

    @patch("api.getList")
    def test_upstream_http_error_returns_502(self, mock_get):
        mock_get.side_effect = ScraperHTTPError("bad gateway", status_code=503)
        resp = self.get(q="python", l="Raleigh, NC")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(body["error"]["type"], "upstream_error")

    @patch("api.getList")
    def test_generic_scraper_error_returns_502(self, mock_get):
        mock_get.side_effect = ScraperError("something scraper-y went wrong")
        resp = self.get(q="python", l="Raleigh, NC")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(body["error"]["type"], "scraper_error")

    @patch("api.getList")
    def test_unexpected_exception_returns_500(self, mock_get):
        mock_get.side_effect = ValueError("boom")
        resp = self.get(q="python", l="Raleigh, NC")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["type"], "internal_error")
        self.assertEqual(body["data"], [])


class TestScraperExceptionHierarchy(unittest.TestCase):
    def test_timeout_is_scraper_error(self):
        self.assertTrue(issubclass(ScraperTimeoutError, ScraperError))

    def test_http_error_is_scraper_error(self):
        self.assertTrue(issubclass(ScraperHTTPError, ScraperError))

    def test_parse_error_is_scraper_error(self):
        self.assertTrue(issubclass(ScraperParseError, ScraperError))

    def test_http_error_stores_status(self):
        err = ScraperHTTPError("nope", status_code=503)
        self.assertEqual(err.status_code, 503)


class TestScraperFieldResilience(unittest.TestCase):
    def test_safe_text_none_tag(self):
        self.assertEqual(safe_text(None), "")

    def test_full_card(self):
        job = parse_card(make_card())
        self.assertEqual(job["title"], "Software Engineer")
        self.assertEqual(job["company"], "Acme Corp")
        self.assertEqual(job["location"], "Raleigh, NC")
        self.assertEqual(job["salary"], "$120,000 a year")
        self.assertEqual(job["summary"], "Build great software.")

    def test_missing_company_defaults_to_unknown(self):
        job = parse_card(make_card(company=False))
        self.assertIsNotNone(job)
        self.assertEqual(job["company"], "Unknown")
        self.assertEqual(job["title"], "Software Engineer")

    def test_missing_location_defaults_to_na(self):
        job = parse_card(make_card(location=False))
        self.assertIsNotNone(job)
        self.assertEqual(job["location"], "N/A")

    def test_missing_salary_defaults_to_empty(self):
        job = parse_card(make_card(salary=False))
        self.assertIsNotNone(job)
        self.assertEqual(job["salary"], "")

    def test_no_title_returns_none(self):
        self.assertIsNone(parse_card(make_card(title=False)))


if __name__ == "__main__":
    unittest.main()
