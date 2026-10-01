from django.urls import path

from apps.identity.views import InvitationAcceptView, LoginView, SessionView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("session/", SessionView.as_view(), name="auth-session"),
    path("invitations/accept/", InvitationAcceptView.as_view(), name="invitation-accept"),
]
