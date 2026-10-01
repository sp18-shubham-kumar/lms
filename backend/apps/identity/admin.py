from django.contrib import admin

from apps.identity.models import IdentityProvider, Invitation, Membership, OrgUnit, Person, Tenant

admin.site.register([Person, Tenant, OrgUnit, Membership, IdentityProvider, Invitation])
