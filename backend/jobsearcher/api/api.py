"""Flask entrypoint for the Job Searcher backend.

This stays intentionally thin: it reads request parameters, delegates the actual
work to the scraper package, and formats the result through the shared response
helpers. All scraping and formatting logic lives outside this file.
"""
from flask import Flask, request
from flask_cors import CORS

import responses
from scraper import ScraperError, get_jobs

app = Flask(__name__)
CORS(app)


@app.route("/retrieveJobs", methods=["GET"])
def retrieve_jobs():
    """Return scraped job listings as JSON.

    Optional query params override the defaults defined in config.py:
      q       - search keywords
      l       - location
      radius  - search radius in miles
      pages   - number of result pages to fetch
    """
    try:
        jobs = get_jobs(
            query=request.args.get("q"),
            location=request.args.get("l"),
            radius=request.args.get("radius", type=int),
            pages=request.args.get("pages", type=int),
        )
    except ScraperError as exc:
        return responses.error_response(str(exc))

    return responses.job_list_response(jobs)
