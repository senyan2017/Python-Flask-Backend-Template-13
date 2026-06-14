"""Flask application entry point.

This file contains *only* route definitions and request/response plumbing.
All scraping logic lives in the ``scraper`` package.
"""

from flask import Flask, request
from flask_cors import CORS

from config import DEFAULT_LOCATION, DEFAULT_QUERY, DEFAULT_RADIUS, MAX_PAGE_COUNT
from responses import error_response, success_response
from scraper import get_jobs

app = Flask(__name__)
CORS(app)


@app.route("/retrieveJobs", methods=["GET"])
def retrieve_jobs():
    """GET /retrieveJobs

    Optional query parameters:
        q        – job search term   (default: from config)
        l        – location filter   (default: from config)
        radius   – search radius     (default: from config)
        pages    – number of pages   (default: 3, max: 10)
    """
    query = request.args.get("q", DEFAULT_QUERY)
    location = request.args.get("l", DEFAULT_LOCATION)

    try:
        radius = int(request.args.get("radius", DEFAULT_RADIUS))
    except (TypeError, ValueError):
        return error_response("'radius' must be an integer.", 400)

    try:
        page_count = int(request.args.get("pages", 3))
    except (TypeError, ValueError):
        return error_response("'pages' must be an integer.", 400)

    if page_count < 1 or page_count > MAX_PAGE_COUNT:
        return error_response(
            f"'pages' must be between 1 and {MAX_PAGE_COUNT}.", 400
        )

    try:
        jobs = get_jobs(
            query=query,
            location=location,
            radius=radius,
            page_count=page_count,
        )
    except Exception as exc:
        return error_response(f"Scraping failed: {exc}", 500)

    return success_response(jobs)


if __name__ == "__main__":
    app.run(debug=True)
