from flask import Flask, request, jsonify
from flask_cors import CORS

from indeedScraper import (
    getList,
    ScraperError,
    ScraperTimeoutError,
    ScraperHTTPError,
    ScraperParseError,
)

## This file is the Flask GET API endpoint for the Backend PackHacks workshop.
## /retrieveJobs validates the incoming search, runs the Indeed scraper, and always
## answers with the same JSON envelope so the frontend never has to guess whether it
## received a list of jobs or an error string.
app = Flask(__name__)
CORS(app)

## Validation bounds. Keeping the keyword/location short and the radius in a sane range
## stops obviously bad input from ever reaching the scraper.
MAX_KEYWORD_LENGTH = 100
MAX_LOCATION_LENGTH = 100
MIN_RADIUS = 0
MAX_RADIUS = 100
DEFAULT_RADIUS = 50


class ValidationError(Exception):
    """Raised when the incoming query parameters fail validation."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _envelope(status, data=None, error=None):
    """Build the single response shape used for every outcome.

    ``data`` is always a list and ``error`` is always present (``None`` on
    success, an object on failure), so the client can rely on a stable schema.
    """
    data = data if data else []
    return {
        "status": status,
        "count": len(data),
        "data": data,
        "error": error,
    }


def _success(jobs):
    return jsonify(_envelope("success", data=jobs, error=None))


def _failure(error_type, message):
    body = _envelope("error", data=[], error={"type": error_type, "message": message})
    return jsonify(body)


def _validate_params(args):
    """Validate and normalize the query string. Returns ``(keyword, location,
    radius)`` or raises ``ValidationError``."""
    keyword = (args.get("q") or "").strip()
    if not keyword:
        raise ValidationError("Query parameter 'q' (keyword) is required and cannot be empty.")
    if len(keyword) > MAX_KEYWORD_LENGTH:
        raise ValidationError(
            "Query parameter 'q' is too long (max {} characters).".format(MAX_KEYWORD_LENGTH)
        )

    location = (args.get("l") or "").strip()
    if not location:
        raise ValidationError("Query parameter 'l' (location) is required and cannot be empty.")
    if len(location) > MAX_LOCATION_LENGTH:
        raise ValidationError(
            "Query parameter 'l' is too long (max {} characters).".format(MAX_LOCATION_LENGTH)
        )

    radius = DEFAULT_RADIUS
    radius_raw = args.get("radius")
    if radius_raw is not None and radius_raw.strip() != "":
        try:
            radius = int(radius_raw)
        except (TypeError, ValueError):
            raise ValidationError("Query parameter 'radius' must be an integer.")
        if radius < MIN_RADIUS or radius > MAX_RADIUS:
            raise ValidationError(
                "Query parameter 'radius' must be between {} and {}.".format(MIN_RADIUS, MAX_RADIUS)
            )

    return keyword, location, radius


## /retrieveJobs is the API GET endpoint that returns the list of jobs to the caller.
## It validates input, runs the Indeed scraper, and returns a uniform JSON envelope.
@app.route("/retrieveJobs", methods=["GET"])
def getJobs():
    # 1) Validate input before touching the scraper.
    try:
        keyword, location, radius = _validate_params(request.args)
    except ValidationError as exc:
        return _failure("invalid_request", exc.message), 400

    # 2) Run the scraper, mapping each distinct failure mode to a distinct status.
    #    Subclasses are caught before the ScraperError base class on purpose.
    try:
        jobs = getList(keyword, location, radius=radius)
    except ScraperTimeoutError as exc:
        return _failure("timeout", str(exc)), 504
    except ScraperHTTPError as exc:
        return _failure("upstream_error", str(exc)), 502
    except ScraperParseError as exc:
        return _failure("parse_error", str(exc)), 502
    except ScraperError as exc:
        return _failure("scraper_error", str(exc)), 502
    except Exception:
        return _failure("internal_error", "Unexpected server error."), 500

    # 3) Success -- including the empty-result case, which is a 200 with an empty list.
    return _success(jobs), 200


if __name__ == "__main__":
    app.run(debug=True)
