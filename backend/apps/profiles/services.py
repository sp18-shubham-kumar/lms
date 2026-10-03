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

- gap_report(membership, job_profile) -> dict
    Per-requirement gap list (met/close/not_started) plus readiness_pct, for the
    learner gap view and the manager's view of one member.

- ensure_editable(job_profile)
    Raise ProfileNotEditable unless the profile is a draft. Published and retired
    versions are never mutated in place; edit a new draft version instead.

- recompute_for_membership(membership)
    Recompute readiness for all job profiles that have a ReadinessSnapshot for
    this membership (or any profile that has a requirement involving a skill this
    member has an assertion for).
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone


class ProfileNotEditable(Exception):
    """A published or retired job profile was asked to change in place."""


def ensure_editable(job_profile: Any) -> None:
    """Only drafts are mutable; published/retired versions are pinned by snapshots."""
    if job_profile.status != "draft":
        raise ProfileNotEditable(
            f"This profile is {job_profile.status} (v{job_profile.version}) and can't be "
            "changed in place. Create a new version to edit it."
        )


def _best_assertion_levels(membership: Any) -> dict[Any, int]:
    """skill_id -> highest verified (SkillAssertion) level for this membership."""
    from apps.skills.models import SkillAssertion

    levels: dict[Any, int] = {}
    for assertion in SkillAssertion.all_tenants.filter(membership=membership):
        existing = levels.get(assertion.skill_id)
        if existing is None or assertion.level > existing:
            levels[assertion.skill_id] = assertion.level
    return levels


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

    # Load all requirements for this profile.
    requirements = list(
        ProfileRequirement.all_tenants.filter(job_profile=job_profile).select_related("skill")
    )
    assertions_by_skill = _best_assertion_levels(membership)

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


def gap_report(membership: Any, job_profile: Any) -> dict[str, Any]:
    """
    The per-requirement gap between a member's verified levels and a job profile.

    Refreshes the readiness snapshot, then lists every requirement (core, supporting,
    optional) as met / close (some verified level, below target) / not_started.
    Unmet requirements come first, smallest gap first ("closest to done"); met last.
    """
    from apps.profiles.models import ProfileRequirement

    snapshot = compute_readiness(membership, job_profile)
    levels = _best_assertion_levels(membership)

    items = []
    for req in ProfileRequirement.all_tenants.filter(job_profile=job_profile).select_related(
        "skill"
    ):
        current = levels.get(req.skill_id)
        is_met = current is not None and current >= req.min_level
        if is_met:
            req_status = "met"
        elif current is not None:
            req_status = "close"
        else:
            req_status = "not_started"
        gap = 0 if is_met else req.min_level - (current or 0)
        items.append(
            (
                (1 if is_met else 0, gap, req.skill.name),
                {
                    "skill_id": str(req.skill_id),
                    "skill_name": req.skill.name,
                    "criticality": req.criticality,
                    "min_level": req.min_level,
                    "current_level": current,
                    "status": req_status,
                },
            )
        )
    items.sort(key=lambda pair: pair[0])

    return {
        "job_profile": str(job_profile.id),
        "readiness_pct": int(snapshot.met * 100 / snapshot.total) if snapshot.total else 0,
        "met": snapshot.met,
        "total": snapshot.total,
        "requirements": [item for _key, item in items],
    }


def publish_job_profile(job_profile: Any, actor: Any) -> Any:
    """
    Transition a draft job profile to published. Audited. Idempotent in effect
    (publishing a published profile is a no-op success); a retired profile can't be
    republished.
    """
    from core import audit

    if job_profile.status == "retired":
        raise ProfileNotEditable("A retired profile can't be published. Create a new version.")
    if job_profile.status == "published":
        return job_profile
    job_profile.status = "published"
    job_profile.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=actor,
        action="jobprofile.publish",
        resource=job_profile,
        tenant_id=job_profile.tenant_id,
        job_profile_id=str(job_profile.id),
    )
    return job_profile


def new_version_from_profile(job_profile: Any, actor: Any) -> Any:
    """
    Create and return a new draft version of a published (or retired) job profile.

    Raises ProfileNotEditable when called on a draft, or when the lineage
    (tenant, track, grade, title) already has an open draft — one draft at a time.

    The prior version row is retained (readiness snapshots pin the version).
    The new draft copies the title/track/grade and the requirements.
    """
    from django.db import transaction

    from apps.profiles.models import JobProfile, ProfileRequirement
    from core import audit

    lineage = JobProfile.all_tenants.filter(
        tenant_id=job_profile.tenant_id,
        track=job_profile.track,
        grade=job_profile.grade,
        title=job_profile.title,
    )
    if job_profile.status == "draft":
        raise ProfileNotEditable("This profile is already a draft; edit it directly.")
    open_draft = lineage.filter(status="draft").first()
    if open_draft is not None:
        raise ProfileNotEditable(
            f"Version {open_draft.version} is already an open draft of this profile."
        )

    with transaction.atomic():
        next_version = (
            lineage.order_by("-version").values_list("version", flat=True).first()
            or job_profile.version
        ) + 1
        new_profile = JobProfile.objects.create(
            tenant_id=job_profile.tenant_id,
            track=job_profile.track,
            grade=job_profile.grade,
            title=job_profile.title,
            status="draft",
            version=next_version,
        )
        # Copy requirements onto the new version.
        for req in ProfileRequirement.all_tenants.filter(job_profile=job_profile):
            ProfileRequirement.objects.create(
                tenant_id=job_profile.tenant_id,
                job_profile=new_profile,
                skill=req.skill,
                min_level=req.min_level,
                criticality=req.criticality,
            )
    audit.record(
        actor=actor,
        action="jobprofile.new_version",
        resource=new_profile,
        tenant_id=new_profile.tenant_id,
        job_profile_id=str(new_profile.id),
        from_job_profile_id=str(job_profile.id),
        version=next_version,
    )
    return new_profile


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


def best_verified_levels(membership: Any) -> dict[Any, int]:
    """
    Return ``{skill_id: highest verified level}`` for a membership.

    The verified tier is the only readiness source, so other modules that reason
    about a learner's gaps (e.g. learning recommendations) read levels here rather
    than querying ``SkillAssertion`` directly.
    """
    from apps.skills.models import SkillAssertion

    levels: dict[Any, int] = {}
    for skill_id, level in SkillAssertion.all_tenants.filter(membership=membership).values_list(
        "skill_id", "level"
    ):
        if level > levels.get(skill_id, 0):
            levels[skill_id] = level
    return levels
