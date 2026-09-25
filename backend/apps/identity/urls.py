from django.urls import path

from apps.identity.views import LoginView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
]
