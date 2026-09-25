from django.urls import path

from apps.identity.views import LoginView, SessionView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("session/", SessionView.as_view(), name="auth-session"),
]
