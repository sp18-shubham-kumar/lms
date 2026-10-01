from django.urls import path

from apps.identity.views import PeopleListView

urlpatterns = [
    path("people/", PeopleListView.as_view(), name="people-list"),
]
