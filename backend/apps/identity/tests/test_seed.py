import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_creates_two_tenants():
    from apps.identity.models import Membership, Tenant

    call_command("seed_demo")
    call_command("seed_demo")  # second run must not duplicate
    assert Tenant.objects.count() == 2
    # The shared person has a membership in both tenants.
    from django.contrib.auth import get_user_model

    Person = get_user_model()
    shared = Person.objects.get(email="dana@shared.test")
    assert Membership.all_tenants.filter(person=shared).count() == 2
