"""Unified JSON response helpers.

Every route should return data through these helpers so the API's
envelope format, status codes, and error shape stay consistent.
"""

from flask import jsonify

HTTP_ACCEPTED = 202
HTTP_BAD_REQUEST = 400
HTTP_SERVER_ERROR = 500


def success_response(data, status_code: int = HTTP_ACCEPTED):
    """Wrap *data* in the standard success envelope."""
    body = jsonify({"status": "success", "data": data})
    body.status_code = status_code
    return body


def error_response(message: str, status_code: int = HTTP_SERVER_ERROR):
    """Return a standard error envelope."""
    body = jsonify({"status": "error", "message": message})
    body.status_code = status_code
    return body
