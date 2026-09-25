from django.contrib import admin

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant

admin.site.register([Capability, Role, RoleCapability, RoleGrant])
