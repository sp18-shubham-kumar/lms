from django import forms
from django.contrib import admin

from apps.identity.models import (
    IdentityProvider,
    Invitation,
    Membership,
    OrgUnit,
    Person,
    Tenant,
)
from core.admin import AllTenantsModelAdmin

admin.site.register([Tenant, OrgUnit, IdentityProvider])


class PersonAdminForm(forms.ModelForm):
    """Hash a new password. A blank password leaves the stored hash in place."""

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Stored as a hash. Leave blank to keep the current password.",
    )

    class Meta:
        model = Person
        fields = (
            "email",
            "display_name",
            "did",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "groups",
            "user_permissions",
        )

    def save(self, commit: bool = True) -> Person:
        person: Person = super().save(commit=False)
        raw_password = self.cleaned_data.get("password") or ""
        if raw_password:
            person.set_password(raw_password)
        elif person.pk:
            person.password = Person.objects.get(pk=person.pk).password
        else:
            person.set_unusable_password()
        if commit:
            person.save()
            self.save_m2m()
        return person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    form = PersonAdminForm
    list_display = ("email", "display_name", "is_active", "is_staff")
    search_fields = ("email", "display_name")


@admin.register(Membership)
class MembershipAdmin(AllTenantsModelAdmin):
    list_display = ("person", "tenant", "status", "employee_ref")
    search_fields = ("person__email", "employee_ref", "tenant__slug")
    list_filter = ("status",)


@admin.register(Invitation)
class InvitationAdmin(AllTenantsModelAdmin):
    list_display = ("email", "tenant", "role", "status", "expires_at")
    search_fields = ("email", "tenant__slug")
    list_filter = ("status",)
