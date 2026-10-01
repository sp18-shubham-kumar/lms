"""Routes for the profiles app."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.profiles.views import (
    HeatmapView,
    JobProfileViewSet,
    MeReadinessView,
    TeamReadinessView,
    TrackViewSet,
)

router = DefaultRouter()
router.register("tracks", TrackViewSet, basename="track")
router.register("job-profiles", JobProfileViewSet, basename="job-profile")
router.register("readiness", TeamReadinessView, basename="team-readiness")

urlpatterns = router.urls + [
    path("me/readiness/", MeReadinessView.as_view(), name="me-readiness"),
    path("heatmap/", HeatmapView.as_view(), name="heatmap"),
]
