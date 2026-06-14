"""Job Searcher API — Flask application.

Endpoints:
    GET /retrieveJobs?q=<query>&location=<loc>&page=<n>&page_size=<n>&source=<name>
    GET /sources
    GET /health

Query Parameters (all optional):
    q          — search keyword (e.g. "python developer")
    location   — location filter (e.g. "San Francisco" or "Remote")
    page       — page number, default 1
    page_size  — items per page, default 20, max 100
    source     — restrict to one scraper source (e.g. "remotive", "indeed")
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from flask_cors import CORS

from scrapers import IndeedScraper, RemotiveScraper, ScraperRegistry

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Scraper registry — add / remove sources here
# ---------------------------------------------------------------------------
registry = ScraperRegistry()
registry.register(RemotiveScraper())
registry.register(IndeedScraper())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_int(name: str, default: int, min_val: int, max_val: int) -> int:
    """Safely parse an integer query parameter with bounds."""
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(min_val, min(value, max_val))


def _ok(payload: dict, status: int = 200):
    return jsonify(payload), status


def _error(message: str, status: int):
    return jsonify({"error": message, "jobs": [], "total": 0}), status


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/retrieveJobs", methods=["GET"])
def retrieve_jobs():
    """Main job-search endpoint."""
    query = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    page = _parse_int("page", 1, 1, 10_000)
    page_size = _parse_int("page_size", 20, 1, 100)
    source = request.args.get("source", "").strip() or None

    if source and source not in registry.sources:
        return _error(
            f"Unknown source '{source}'. Available: {registry.sources}",
            400,
        )

    result = registry.search(
        query=query,
        location=location,
        page=page,
        page_size=page_size,
        source=source,
    )

    status = 200
    if result["total"] == 0 and result["errors"]:
        # All sources errored out — still return 200 with empty jobs so the
        # frontend can render gracefully, but surface the errors.
        status = 207  # Multi-Status — partial / degraded
    elif result["total"] == 0:
        status = 200  # legitimate zero results is NOT an error

    return _ok(result, status)


@app.route("/sources", methods=["GET"])
def list_sources():
    """Return the list of registered scraper sources."""
    return _ok({"sources": registry.sources})


@app.route("/health", methods=["GET"])
def health():
    """Simple liveness probe."""
    return _ok({"status": "ok"})


# ---------------------------------------------------------------------------
# Entry point (for `python api.py`; flask run uses .flaskenv)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
