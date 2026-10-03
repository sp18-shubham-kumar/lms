"""Local development settings."""

from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK

DEBUG = True

# Vite moves to the next free port (5174, 5175, ...) when 5173 is taken. Accept any
# localhost port in dev so login isn't silently blocked by CORS.
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(localhost|127\.0\.0\.1):\d+$"]

# Browsable API is convenient locally.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}
