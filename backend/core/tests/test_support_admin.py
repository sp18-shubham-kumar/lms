from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.utils import timezone


def _seed() -> None:
    from apps.authz.models import Role, RoleGrant
    from apps.identity.models import Invitation, Membership, Tenant

    Person = get_user_model()
    Person.objects.create_superuser(
        email="root@support.test", display_name="Root", password="pw-12345"
    )
    for slug in ("acme", "north"):
        tenant = Tenant.objects.create(slug=slug, name=slug.title(), status="active")
        person = Person.objects.create_user(
            email=f"member@{slug}.test", display_name=slug, password="pw-12345"
        )
        role = Role.all_tenants.create(tenant=tenant, name="Learner", is_system=True)
        Membership.all_tenants.create(person=person, tenant=tenant, status="active")
        RoleGrant.all_tenants.create(
            tenant=tenant,
            principal_type="person",
            principal_id=person.id,
            role=role,
        )
        Invitation.all_tenants.create(
            tenant=tenant,
            email=f"invite@{slug}.test",
            role=role,
            token_hash=slug.ljust(64, "x"),
            expires_at=timezone.now() + timedelta(days=7),
            status="pending",
        )


def _staff_client() -> Client:
    client = Client()
    client.force_login(get_user_model().objects.get(email="root@support.test"))
    return client


@pytest.mark.django_db
def test_support_admin_lists_every_tenant_while_objects_stays_scoped():
    from apps.authz.models import Role, RoleGrant
    from apps.identity.models import Invitation, Membership

    _seed()
    # No tenant is in context, so a request handler's manager still sees nothing.
    assert Role.objects.count() == 0
    assert Membership.objects.count() == 0
    assert RoleGrant.objects.count() == 0
    assert Invitation.objects.count() == 0

    client = _staff_client()
    for url in (
        "/admin/authz/role/",
        "/admin/authz/rolegrant/",
        "/admin/identity/membership/",
        "/admin/identity/invitation/",
    ):
        response = client.get(url)
        assert response.status_code == 200
        assert response.context["cl"].queryset.count() == 2


@pytest.mark.django_db
def test_role_grant_form_can_choose_a_role_from_any_tenant():
    from django.contrib import admin

    from apps.authz.models import Role, RoleGrant

    _seed()
    request = RequestFactory().get("/admin/authz/rolegrant/add/")
    request.user = get_user_model().objects.get(email="root@support.test")
    form_class = admin.site._registry[RoleGrant].get_form(request)
    form = form_class()
    assert set(form.fields["role"].queryset.values_list("tenant__slug", flat=True)) == {
        "acme",
        "north",
    }
    assert Role.objects.count() == 0


@pytest.mark.django_db
def test_person_admin_hashes_a_new_password_and_keeps_a_blank_one():
    from django.contrib import admin

    from apps.identity.admin import PersonAdminForm
    from apps.identity.models import Person

    request = RequestFactory().post("/admin/identity/person/add/")
    request.user = Person.objects.create_superuser(
        email="root@support.test", display_name="Root", password="pw-12345"
    )
    person_admin = admin.site._registry[Person]
    created = PersonAdminForm(
        data={
            "email": "ada@support.test",
            "display_name": "Ada",
            "did": "",
            "password": "Repair-pass-123",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
        }
    )
    assert created.is_valid(), created.errors
    person = created.save(commit=False)
    person_admin.save_model(request, person, created, change=False)
    person.refresh_from_db()
    assert person.password != "Repair-pass-123"
    assert person.check_password("Repair-pass-123")

    unchanged = PersonAdminForm(
        data={
            "email": person.email,
            "display_name": "Ada Lovelace",
            "did": "",
            "password": "",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
        },
        instance=person,
    )
    assert unchanged.is_valid(), unchanged.errors
    saved = unchanged.save(commit=False)
    person_admin.save_model(request, saved, unchanged, change=True)
    saved.refresh_from_db()
    assert saved.display_name == "Ada Lovelace"
    assert saved.check_password("Repair-pass-123")
