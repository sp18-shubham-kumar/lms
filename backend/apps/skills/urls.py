"""Routes for the skills app."""

from rest_framework.routers import DefaultRouter

from apps.skills.views import SkillDomainViewSet, SkillViewSet

router = DefaultRouter()
router.register("domains", SkillDomainViewSet, basename="skill-domain")
router.register("skills", SkillViewSet, basename="skill")

urlpatterns = router.urls
