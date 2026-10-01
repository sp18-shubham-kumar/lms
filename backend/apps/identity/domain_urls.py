from django.urls import path

from apps.identity.views import InvitationListCreateView, MemberImportView, PeopleListView

urlpatterns = [
    path("people/", PeopleListView.as_view(), name="people-list"),
    path("members/import/", MemberImportView.as_view(), name="member-import"),
    path("invitations/", InvitationListCreateView.as_view(), name="invitations"),
]
