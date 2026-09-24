"""
Shared pytest fixtures.

Add tenant/person/membership factories here as the identity app lands so every
test can spin up isolated tenants cheaply.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF API client."""
    return APIClient()
