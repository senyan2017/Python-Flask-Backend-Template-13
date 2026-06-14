"""Flask REST API for the Job Searcher backend (PackHacks workshop).

The endpoint ``GET /retrieveJobs`` takes the search criteria as query params,
runs the chosen site scraper, and returns one consistent JSON envelope:

    {
      "status": "ok" | "error",
      "source": "indeed",
      "query":  {"q": "...", "location": "...", "source": "...",
                 "page": 1, "limit": 25},
      "count":  <jobs on this page>,
      "total":  <best-effort total matches>,
      "jobs":   [ {title, company, location, url, summary, salary,
                   source, posted, tags}, ... ],
      "error":  null | {"type": "...", "message": "..."}
    }

All scraping logic lives in the ``scrapers`` package, so this file only deals
with HTTP: parsing params, shaping the response, and turning failures into a
clean payload instead of a raw 500.

Originally authored for the workshop by Travis Walter; reworked into a real,
configurable implementation.
"""

from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS

import scrapers

app = Flask(__name__)
CORS(app)  # allow the React frontend (different origin) to call this API

DEFAULT_SOURCE = "indeed"
DEFAULT_LIMIT = 25
MAX_LIMIT = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_int(value, *, default: int, minimum: int, maximum: int = None) -> int:
    """Parse ``value`` to an int, falling back to ``default`` and clamping.

    Bad input (None, "abc", "-3") never raises -- the frontend should not be
    able to 500 the API by sending a junk ``page``/``limit``.
    """
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if result < minimum:
        result = minimum
    if maximum is not None and result > maximum:
        result = maximum
    return result


def _envelope(status, source, query, *, jobs=None, total=0, error=None):
    jobs = jobs or []
    return {
        "status": status,
        "source": source,
        "query": query,
        "count": len(jobs),
        "total": total,
        "jobs": jobs,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/retrieveJobs", methods=["GET"])
def retrieve_jobs():
    # Accept both short (Indeed-style q/l) and long aliases for friendliness.
    query = (request.args.get("q") or request.args.get("query") or "").strip()
    location = (
        request.args.get("l") or request.args.get("location") or ""
    ).strip()
    source = (request.args.get("source") or DEFAULT_SOURCE).strip().lower()
    page = _to_int(request.args.get("page"), default=1, minimum=1)
    limit = _to_int(
        request.args.get("limit"),
        default=DEFAULT_LIMIT,
        minimum=1,
        maximum=MAX_LIMIT,
    )

    query_echo = {
        "q": query,
        "location": location,
        "source": source,
        "page": page,
        "limit": limit,
    }

    scraper = scrapers.get_scraper(source)
    if scraper is None:
        return (
            jsonify(
                _envelope(
                    "error",
                    source,
                    query_echo,
                    error={
                        "type": "unknown_source",
                        "message": (
                            f"Unknown source '{source}'. Available sources: "
                            f"{scrapers.available_sources()}."
                        ),
                    },
                )
            ),
            400,
        )

    try:
        result = scraper.search(query, location, page=page, limit=limit)
    except scrapers.ScraperError as exc:
        # Site blocked us / changed layout / network failed: respond cleanly so
        # the frontend can tell the difference from "no results".
        return (
            jsonify(
                _envelope(
                    "error",
                    source,
                    query_echo,
                    error={"type": exc.error_type, "message": str(exc)},
                )
            ),
            502,
        )

    jobs = [job.to_dict() for job in result.jobs]
    return (
        jsonify(
            _envelope("ok", source, query_echo, jobs=jobs, total=result.total)
        ),
        200,
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "sources": scrapers.available_sources()})


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "service": "Job Searcher API",
            "endpoints": {
                "/retrieveJobs": "GET job listings",
                "/health": "service + available sources",
            },
            "params": {
                "q": "search keywords (alias: query)",
                "l": "location (alias: location)",
                "source": f"one of {scrapers.available_sources()}",
                "page": "page number (default 1)",
                "limit": f"results per page (default {DEFAULT_LIMIT}, "
                f"max {MAX_LIMIT})",
            },
            "examples": [
                "/retrieveJobs?source=remoteok&q=python",
                "/retrieveJobs?q=Software+Engineer&l=Raleigh%2C+NC&page=1",
            ],
        }
    )


# ---------------------------------------------------------------------------
# Error handlers -- always return JSON, never an HTML error page
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def _not_found(_err):
    return (
        jsonify(
            {
                "status": "error",
                "error": {
                    "type": "not_found",
                    "message": "Unknown endpoint. Try GET /retrieveJobs.",
                },
            }
        ),
        404,
    )


@app.errorhandler(405)
def _method_not_allowed(_err):
    return (
        jsonify(
            {
                "status": "error",
                "error": {
                    "type": "method_not_allowed",
                    "message": "This endpoint only supports GET.",
                },
            }
        ),
        405,
    )


@app.errorhandler(500)
def _internal_error(_err):
    return (
        jsonify(
            {
                "status": "error",
                "error": {
                    "type": "internal_error",
                    "message": "Something went wrong while handling the "
                    "request.",
                },
            }
        ),
        500,
    )


if __name__ == "__main__":
    # Allows `python api.py` in addition to `flask run`.
    app.run(host="127.0.0.1", port=5000, debug=True)
