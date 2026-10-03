from typing import Any

from django.contrib import admin

from apps.learning.models import LearningProgress, LearningResource, ResourceSkill
from core.admin import AllTenantsModelAdmin


class ResourceSkillInline(admin.TabularInline):
    model = ResourceSkill
    extra = 0

    def get_queryset(self, request: Any) -> Any:
        return ResourceSkill.all_tenants.all()


@admin.register(LearningResource)
class LearningResourceAdmin(AllTenantsModelAdmin):
    list_display = ("title", "kind", "status", "module_count", "tenant")
    search_fields = ("title", "tenant__slug")
    list_filter = ("kind", "status")
    inlines = [ResourceSkillInline]


@admin.register(LearningProgress)
class LearningProgressAdmin(AllTenantsModelAdmin):
    list_display = ("membership", "resource", "status", "completed_modules", "tenant")
    list_filter = ("status",)
