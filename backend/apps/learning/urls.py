"""Routes for the learning app."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.learning.views import LearningResourceViewSet, MyProgressViewSet, MyRecommendationsView

router = DefaultRouter()
router.register("resources", LearningResourceViewSet, basename="learning-resource")
router.register("me/progress", MyProgressViewSet, basename="learning-progress")

urlpatterns = router.urls + [
    path("me/recommendations/", MyRecommendationsView.as_view(), name="learning-recommendations"),
]
