from flask import Flask, request, jsonify
from flask_cors import CORS

from indeedScraper import getList, ScraperTimeoutError, ScraperHttpError, ScraperError

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data, message="success"):
    """Return a unified success response (HTTP 200)."""
    return jsonify({"success": True, "message": message, "data": data, "error": None}), 200


def _error(status_code, error_code, message, details=None):
    """Return a unified error response.

    The response body always has the same shape so that frontends never need
    to guess the structure:
        { "success": false, "message": str, "data": [], "error": { code, details } }
    """
    body = {
        "success": False,
        "message": message,
        "data": [],
        "error": {"code": error_code, "details": details},
    }
    return jsonify(body), status_code


def _validate_params(args):
    """Validate query parameters and return (keyword, location, radius) or raise ValueError."""
    keyword = (args.get("keyword") or "").strip()
    location = (args.get("location") or "").strip()
    radius_raw = args.get("radius", "25")

    if not keyword:
        raise ValueError("'keyword' is required and must not be empty.")
    if not location:
        raise ValueError("'location' is required and must not be empty.")

    # Sanitize: reject control characters and absurdly long input
    if len(keyword) > 200 or len(location) > 200:
        raise ValueError("Parameters must not exceed 200 characters.")

    try:
        radius = int(radius_raw)
        if radius < 0 or radius > 200:
            raise ValueError("'radius' must be between 0 and 200.")
    except (TypeError, ValueError):
        raise ValueError("'radius' must be a valid integer between 0 and 200.")

    return keyword, location, radius


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/retrieveJobs', methods=['GET'])
def getJobs():
    """GET /retrieveJobs?keyword=...&location=...&radius=25

    Returns a list of job postings scraped from Indeed.

    Success (200):
        { "success": true, "message": "success", "data": [...], "error": null }

    Client error (400):
        { "success": false, "message": "...", "data": [], "error": { "code": "INVALID_PARAMS", ... } }

    Upstream error (502):
        { "success": false, "message": "...", "data": [], "error": { "code": "SCRAPER_ERROR", ... } }

    Timeout (504):
        { "success": false, "message": "...", "data": [], "error": { "code": "SCRAPER_TIMEOUT", ... } }
    """
    # --- Input validation ---
    try:
        keyword, location, radius = _validate_params(request.args)
    except ValueError as exc:
        return _error(400, "INVALID_PARAMS", str(exc))

    # --- Scraping ---
    try:
        jobs = getList(keyword=keyword, location=location, radius=radius)
    except ScraperTimeoutError as exc:
        return _error(
            504,
            "SCRAPER_TIMEOUT",
            "The request to Indeed timed out. Please try again later.",
            details=str(exc),
        )
    except ScraperHttpError as exc:
        return _error(
            502,
            "SCRAPER_ERROR",
            "Indeed returned an error. Please try again later.",
            details=f"HTTP {exc.status_code}",
        )
    except ScraperError as exc:
        return _error(
            502,
            "SCRAPER_ERROR",
            "An unexpected error occurred while scraping Indeed.",
            details=str(exc),
        )
    except Exception as exc:
        return _error(
            500,
            "INTERNAL_ERROR",
            "An internal server error occurred.",
            details=str(exc),
        )

    # --- Empty results are NOT an error — just an empty list ---
    return _ok(jobs, message=f"Found {len(jobs)} job(s).")
