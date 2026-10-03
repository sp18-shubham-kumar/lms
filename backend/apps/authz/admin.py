from django.contrib import admin

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
from core.admin import AllTenantsModelAdmin

admin.site.register([Capability, RoleCapability])


@admin.register(Role)
class RoleAdmin(AllTenantsModelAdmin):
    list_display = ("name", "tenant", "is_system")
    search_fields = ("name", "tenant__slug")


@admin.register(RoleGrant)
class RoleGrantAdmin(AllTenantsModelAdmin):
    list_display = ("role", "principal_type", "principal_id", "tenant")
    search_fields = ("role__name", "tenant__slug")
