from django.urls import path

from apps.identity.invitation_views import (
    InvitationCancelView,
    InvitationListView,
    InvitationResendView,
)
from apps.identity.profile_views import MemberOffboardView, PersonProfileView
from apps.identity.views import MemberImportView, OrgUnitListView, PeopleListView

urlpatterns = [
    path("people/", PeopleListView.as_view(), name="people-list"),
    path("people/me/", PersonProfileView.as_view(), name="my-profile"),
    path("people/<uuid:person_id>/", PersonProfileView.as_view(), name="person-profile"),
    path(
        "people/<uuid:person_id>/offboard/",
        MemberOffboardView.as_view(),
        name="member-offboard",
    ),
    path("org-units/", OrgUnitListView.as_view(), name="org-unit-list"),
    path("members/import/", MemberImportView.as_view(), name="member-import"),
    path("invitations/", InvitationListView.as_view(), name="invitation-list"),
    path("invitations/<uuid:id>/resend/", InvitationResendView.as_view(), name="invitation-resend"),
    path("invitations/<uuid:id>/", InvitationCancelView.as_view(), name="invitation-cancel"),
]
