"""Routes for the authz app (role management + grant management)."""

from rest_framework.routers import DefaultRouter

from apps.authz.views import RoleGrantViewSet, RoleViewSet

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("grants", RoleGrantViewSet, basename="role-grant")

urlpatterns = router.urls
