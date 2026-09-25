import pytest
from django.contrib.auth import get_user_model

Person = get_user_model()


@pytest.mark.django_db
def test_create_user_sets_email_and_password():
    person = Person.objects.create_user(
        email="alice@acme.test", display_name="Alice", password="pw-12345"
    )
    assert person.email == "alice@acme.test"
    assert person.display_name == "Alice"
    assert person.check_password("pw-12345")
    assert person.is_active is True
    assert person.is_staff is False


@pytest.mark.django_db
def test_create_superuser_flags():
    admin = Person.objects.create_superuser(
        email="root@acme.test", display_name="Root", password="pw-12345"
    )
    assert admin.is_staff and admin.is_superuser


@pytest.mark.django_db
def test_email_is_the_username_field():
    assert Person.USERNAME_FIELD == "email"
