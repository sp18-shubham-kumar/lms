from django.contrib import admin

from apps.identity.models import IdentityProvider, Membership, OrgUnit, Person, Tenant

admin.site.register([Person, Tenant, OrgUnit, Membership, IdentityProvider])
