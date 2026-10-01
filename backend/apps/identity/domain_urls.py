from django.urls import path

from apps.identity.invitation_views import (
    InvitationCancelView,
    InvitationListView,
    InvitationResendView,
)
from apps.identity.views import MemberImportView, OrgUnitListView, PeopleListView

urlpatterns = [
    path("people/", PeopleListView.as_view(), name="people-list"),
    path("org-units/", OrgUnitListView.as_view(), name="org-unit-list"),
    path("members/import/", MemberImportView.as_view(), name="member-import"),
    path("invitations/", InvitationListView.as_view(), name="invitation-list"),
    path("invitations/<uuid:id>/resend/", InvitationResendView.as_view(), name="invitation-resend"),
    path("invitations/<uuid:id>/", InvitationCancelView.as_view(), name="invitation-cancel"),
]
