"""Routes for the profiles app."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.profiles.views import (
    HeatmapView,
    JobProfileViewSet,
    MemberReadinessView,
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
    path(
        "members/<uuid:membership_id>/readiness/",
        MemberReadinessView.as_view(),
        name="member-readiness",
    ),
    path("heatmap/", HeatmapView.as_view(), name="heatmap"),
]
