"""Routes for the skills app."""

from rest_framework.routers import DefaultRouter

from apps.skills.views import (
    SelfDeclaredSkillViewSet,
    SkillAssertionViewSet,
    SkillClaimViewSet,
    SkillDomainViewSet,
    SkillViewSet,
    TenantSkillOverrideViewSet,
)

router = DefaultRouter()
# Named prefixes first so they are matched before the empty-prefix skill routes.
# The empty-prefix registration must be last: its detail pattern (?P<pk>[^/.]+)/
# would otherwise swallow "domains/", "me/declarations/", "assertions/", "claims/",
# "overrides/" as PKs.
router.register("domains", SkillDomainViewSet, basename="skill-domain")
router.register("me/declarations", SelfDeclaredSkillViewSet, basename="self-declared-skill")
router.register("assertions", SkillAssertionViewSet, basename="skill-assertion")
router.register("claims", SkillClaimViewSet, basename="skill-claim")
router.register("overrides", TenantSkillOverrideViewSet, basename="skill-override")
router.register("", SkillViewSet, basename="skill")

urlpatterns = router.urls
