"""Routes for the skills app."""

from rest_framework.routers import DefaultRouter

from apps.skills.views import (
    SelfDeclaredSkillViewSet,
    SkillAssertionViewSet,
    SkillDomainViewSet,
    SkillViewSet,
)

router = DefaultRouter()
router.register("domains", SkillDomainViewSet, basename="skill-domain")
router.register("skills", SkillViewSet, basename="skill")
router.register("me/declarations", SelfDeclaredSkillViewSet, basename="self-declared-skill")
router.register("assertions", SkillAssertionViewSet, basename="skill-assertion")

urlpatterns = router.urls
