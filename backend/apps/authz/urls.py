"""Routes for the authz app (role management + grant management)."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.authz.views import CapabilityListView, RoleGrantViewSet, RoleViewSet

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("grants", RoleGrantViewSet, basename="role-grant")

urlpatterns = [
    path("capabilities/", CapabilityListView.as_view(), name="capability-list"),
    *router.urls,
]
