from django.urls import path

from apps.identity.platform_views import TenantProvisionView

urlpatterns = [
    path("tenants/", TenantProvisionView.as_view(), name="platform-tenant-create"),
]
