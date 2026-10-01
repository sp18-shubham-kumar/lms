"""
Root URL configuration.

Everything the SPA talks to lives under /api/. Domain apps expose their own
routers and are included here as they are implemented (see docs/specs/phase-1.md).
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

api_patterns = [
    # Health & schema
    path("", include("core.urls")),
    # Auth (JWT). Tenant-aware login + token refresh.
    path("auth/", include("apps.identity.urls")),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Schema / docs
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Domain apps — uncomment each as it is implemented.
    path("identity/", include("apps.identity.domain_urls")),
    path("authz/", include("apps.authz.urls")),
    path("skills/", include("apps.skills.urls")),
    # path("profiles/", include("apps.profiles.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),  # type: ignore[arg-type]
]
