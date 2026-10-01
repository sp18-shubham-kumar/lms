"""
Profiles service layer — readiness computation.

The readiness engine reads ONLY the verified tier (SkillAssertion) to determine
whether a member meets each requirement. Self-declared skills never gate readiness.

Functions:
- compute_readiness(membership, job_profile) -> ReadinessSnapshot
    For each core ProfileRequirement, check if a SkillAssertion exists with
    level >= min_level. Count met/total over core requirements only.
    Supporting/optional are computed but advisory (not in met/total).
    Persists/updates the snapshot (upsert).

- recompute_for_membership(membership)
    Recompute readiness for all job profiles that have a ReadinessSnapshot for
    this membership (or any profile that has a requirement involving a skill this
    member has an assertion for).
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone


def compute_readiness(membership: Any, job_profile: Any) -> Any:
    """
    Compute and persist a ReadinessSnapshot for a membership against a job_profile.

    Only the verified tier (SkillAssertion) is consulted — self-declarations are
    not considered. Core requirements gate met/total; supporting/optional are
    advisory only.

    This function is safe to call concurrently: it uses update_or_create to
    avoid duplicate rows.
    """
    from apps.profiles.models import ProfileRequirement, ReadinessSnapshot
    from apps.skills.models import SkillAssertion

    # Load all requirements for this profile.
    requirements = list(
        ProfileRequirement.all_tenants.filter(job_profile=job_profile).select_related("skill")
    )

    # Build a lookup of skill_id -> best verified assertion level for this membership.
    assertion_qs = SkillAssertion.all_tenants.filter(membership=membership)
    assertions_by_skill: dict[Any, int] = {}
    for assertion in assertion_qs:
        existing = assertions_by_skill.get(assertion.skill_id)
        if existing is None or assertion.level > existing:
            assertions_by_skill[assertion.skill_id] = assertion.level

    # Tally core requirements.
    met = 0
    total = 0
    blocking_skill_ids = []

    for req in requirements:
        assertion_level = assertions_by_skill.get(req.skill_id)
        is_met = assertion_level is not None and assertion_level >= req.min_level

        if req.criticality == "core":
            total += 1
            if is_met:
                met += 1
            else:
                blocking_skill_ids.append(req.skill_id)
        # supporting/optional: computed but not counted in met/total

    now = timezone.now()
    snapshot, _created = ReadinessSnapshot.all_tenants.update_or_create(
        membership=membership,
        job_profile=job_profile,
        defaults={
            "tenant_id": job_profile.tenant_id,
            "met": met,
            "total": total,
            "blocking_skill_ids": blocking_skill_ids,
            "job_profile_version": job_profile.version,
            "computed_at": now,
        },
    )
    return snapshot


def recompute_for_membership(membership: Any) -> None:
    """
    Recompute readiness snapshots for a membership.

    Targets every job_profile for which a ReadinessSnapshot exists for this
    membership, plus any job profile with a requirement involving a skill this
    member has a verified assertion for.
    """
    from apps.profiles.models import JobProfile, ProfileRequirement, ReadinessSnapshot

    # Find profiles already snapshotted for this membership.
    snapshotted_profile_ids = set(
        ReadinessSnapshot.all_tenants.filter(membership=membership).values_list(
            "job_profile_id", flat=True
        )
    )

    # Find profiles with requirements on skills this member has assertions for.
    from apps.skills.models import SkillAssertion

    asserted_skill_ids = set(
        SkillAssertion.all_tenants.filter(membership=membership).values_list("skill_id", flat=True)
    )
    if asserted_skill_ids:
        profile_ids_from_assertions = set(
            ProfileRequirement.all_tenants.filter(
                skill_id__in=asserted_skill_ids, job_profile__tenant_id=membership.tenant_id
            ).values_list("job_profile_id", flat=True)
        )
    else:
        profile_ids_from_assertions = set()

    all_profile_ids = snapshotted_profile_ids | profile_ids_from_assertions
    if not all_profile_ids:
        return

    for profile in JobProfile.all_tenants.filter(id__in=all_profile_ids):
        compute_readiness(membership, profile)
