"""
Consistent API error envelope.

Every deny/error returns ``{"error": {"code", "detail"}}`` so the frontend can
render actionable messages. The spec is emphatic that "permission denied" with no
reason generates support tickets forever — extend the handler to include the
failing check once ``can()`` reports one.
"""

from __future__ import annotations

from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, "default_code", "error")
    response.data = {
        "error": {
            "code": code,
            "detail": response.data,
        }
    }
    return response
