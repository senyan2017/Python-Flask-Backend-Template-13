"""Single place that decides the shape of every HTTP response.

Centralizing this means changing the response format (or status codes) later is
one edit here rather than across every route. The success payload is kept as a
bare JSON array of job objects to stay compatible with the existing frontend
contract for /retrieveJobs.
"""
from flask import jsonify

# HTTP status codes used by the API, named so routes never sprinkle raw numbers.
HTTP_OK = 200
HTTP_BAD_GATEWAY = 502


def job_list_response(jobs: list):
    """Return the list of jobs as a JSON array (the frontend's contract)."""
    response = jsonify(jobs)
    response.status_code = HTTP_OK
    return response


def error_response(message: str, status: int = HTTP_BAD_GATEWAY):
    """Return a uniform error body so clients can handle failures predictably."""
    response = jsonify({"error": message})
    response.status_code = status
    return response
