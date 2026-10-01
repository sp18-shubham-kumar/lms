from django.urls import path

from apps.identity.views import MemberImportView, OrgUnitListView, PeopleListView

urlpatterns = [
    path("people/", PeopleListView.as_view(), name="people-list"),
    path("org-units/", OrgUnitListView.as_view(), name="org-unit-list"),
    path("members/import/", MemberImportView.as_view(), name="member-import"),
]
