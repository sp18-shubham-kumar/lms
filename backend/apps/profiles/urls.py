"""Routes for the profiles app."""

from rest_framework.routers import DefaultRouter

from apps.profiles.views import JobProfileViewSet, TrackViewSet

router = DefaultRouter()
router.register("tracks", TrackViewSet, basename="track")
router.register("job-profiles", JobProfileViewSet, basename="job-profile")

urlpatterns = router.urls
