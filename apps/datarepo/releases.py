"""Releases: new versions of published datasets (pri-data docs/PUBLISHING_PLAN.md B4, website-backend #125).

A release is uploaded beside the live dataset, reviewed like a dataset (same gate, same two-person rule) and, when
published, replaces the dataset's files and metadata in one transaction while the dataset stays published. The files
of earlier published releases stay downloadable; they are shared with the dataset, not copied, so no stored file is
deleted while a dataset or a release still points at it (models.stored_file_in_use).
"""

import hashlib
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from apps.workflow.permissions import CONTRIBUTOR_ROLES, STAFF_ROLES

from .models import (
    PUBLISH_REQUIRED_FIELDS,
    QA_CHECKLIST_ITEMS,
    DatasetFile,
    DatasetRelease,
    DatasetReleaseFile,
    ReleaseStatus,
)
from .previews import profile_file

# Dataset fields a release's metadata may set. Not the slug (links and citations use it), the access tier (a deliberate
# staff decision, not part of a refresh), the workflow fields or the QA checklist (kept per release).
RELEASE_METADATA_FIELDS = [
    "title", "description", "sub_theme", "geography", "year", "source", "update_frequency", "granularity",
    "time_period", "citation", "code", "summary", "keywords", "source_publisher", "source_document", "source_url",
    "archived_url", "retrieval_date", "source_tier", "collection_method", "source_terms", "period_type",
    "next_update", "methodology", "known_limitations", "lgd_levels", "quality_grade", "license", "steward", "contact",
    "related_publications", "column_dictionary", "provenance", "qa_report",
]

# Who may move a release where: draft -> in_review is the creator's (or staff's) submission, everything else is staff's.
RELEASE_TRANSITIONS = {
    ReleaseStatus.DRAFT: {ReleaseStatus.IN_REVIEW},
    ReleaseStatus.IN_REVIEW: {ReleaseStatus.APPROVED, ReleaseStatus.DRAFT, ReleaseStatus.REJECTED},
    ReleaseStatus.APPROVED: {ReleaseStatus.PUBLISHED, ReleaseStatus.DRAFT, ReleaseStatus.REJECTED},
}

# Version recorded for the live files of a dataset published without a version, when its first release arrives.
UNVERSIONED = "1.0.0"


def version_key(version):
    return tuple(int(part) for part in version.split("."))


def _role(user):
    return getattr(user, "role", None)


def can_release(user, dataset):
    """Who may post a release: editors and admins, and the contributor who created the dataset (pri-pipeline)."""
    role = _role(user)
    return role in STAFF_ROLES or (role in CONTRIBUTOR_ROLES and dataset.created_by_id == user.id)


def can_see_release(user, release):
    """Published releases are the public version history; the others are for staff and their creator."""
    if release.status == ReleaseStatus.PUBLISHED:
        return True
    return _role(user) in STAFF_ROLES or (user.is_authenticated and release.created_by_id == user.id)


def latest_version(dataset):
    """The highest version the dataset has had: its own, or any release that wasn't rejected."""
    versions = [dataset.version or UNVERSIONED] + list(
        dataset.releases.exclude(status=ReleaseStatus.REJECTED).values_list("version", flat=True)
    )
    return max(versions, key=version_key)


def sha256_of(uploaded):
    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    uploaded.seek(0)
    return digest.hexdigest()


def profile_release(release):
    """Row count and columns of the release's main file, like Dataset.save() works them out for a dataset."""
    main = release.main_file
    profile = profile_file(SimpleNamespace(format=release.format, file=main.file)) if main else None
    release.row_count, release.columns = (profile[0], profile[1]) if profile else (None, [])
    release.column_count = len(release.columns) if profile else None
    release.save(update_fields=["row_count", "column_count", "columns"])


def snapshot(dataset):
    """The dataset's current metadata in release form (what the baseline release records)."""
    values = {}
    for name in RELEASE_METADATA_FIELDS:
        if name == "related_publications":
            values[name] = list(dataset.related_publications.values_list("slug", flat=True))
        elif name == "sub_theme":
            values[name] = dataset.sub_theme_id
        elif name == "retrieval_date":
            values[name] = dataset.retrieval_date.isoformat() if dataset.retrieval_date else None
        else:
            values[name] = getattr(dataset, name)
    return values


def ensure_baseline(dataset):
    """Record the dataset's live version as a published release the first time a release is posted, so the files it
    serves now stay downloadable after the new release replaces them. Its files are the dataset's own, not copies."""
    if dataset.releases.exists():
        return None
    baseline = DatasetRelease.objects.create(
        dataset=dataset, version=dataset.version or UNVERSIONED, status=ReleaseStatus.PUBLISHED, format=dataset.format,
        changelog="Version published before releases existed.", metadata=snapshot(dataset),
        qa_checklist=dataset.qa_checklist, row_count=dataset.row_count, column_count=dataset.column_count,
        columns=dataset.columns, created_by=dataset.created_by, approved_by=dataset.approved_by,
        approved_at=dataset.approved_at, published_at=dataset.published_at or timezone.now(),
    )
    if dataset.file:
        DatasetReleaseFile.objects.create(release=baseline, format=dataset.format, file=dataset.file.name,
                                          size=dataset.file_size)
    for extra in dataset.extra_files.all():
        DatasetReleaseFile.objects.create(release=baseline, format=extra.format, file=extra.file.name, size=extra.size)
    return baseline


def publishing_problems(*, status_ok, value, columns, column_dictionary, qa_report, qa_checklist):
    """The PRI Data Framework's publishing gate, shared by datasets and releases: every reason not to publish yet."""
    problems = [] if status_ok is True else [status_ok]
    empty = [name for name in PUBLISH_REQUIRED_FIELDS if value(name) in (None, "")]
    if empty:
        problems.append("these fields are empty: " + ", ".join(empty))
    if value("source_tier") == "4":
        problems.append("tier 4 sources (news, unverified files) are never published")
    labelled = {e.get("name") for e in column_dictionary or [] if str(e.get("label") or "").strip()}
    unlabelled = [c for c in columns or [] if c not in labelled]
    if unlabelled:
        problems.append("these columns have no label in the column dictionary: " + ", ".join(unlabelled))
    if (qa_report or {}).get("passed") is not True:
        problems.append("the automated QA report has not passed (run `pri publish --check`)")
    checklist = qa_checklist or {}
    open_items = [key for key, _ in QA_CHECKLIST_ITEMS if checklist.get(key) is not True]
    if open_items:
        problems.append("the QA checklist is not complete (open: " + ", ".join(open_items) + ")")
    return problems


def release_publish_blocker(release):
    """Why the release can't be published yet, judged on the dataset as it would be after publishing, or None."""
    dataset, meta = release.dataset, release.metadata
    status_ok = True
    if release.status != ReleaseStatus.APPROVED:
        status_ok = f"it must be approved first (it is {release.get_status_display().lower()})"
    elif dataset.status != "published":
        status_ok = "its dataset is not published (publish the dataset itself instead)"

    def value(name):
        if name == "version":
            return release.version
        return meta[name] if name in meta else getattr(dataset, name)

    problems = publishing_problems(
        status_ok=status_ok, value=value, columns=release.columns,
        column_dictionary=meta.get("column_dictionary", dataset.column_dictionary),
        qa_report=meta.get("qa_report"), qa_checklist=release.qa_checklist,
    )
    if not release.main_file:
        problems.append(f"it has no {release.format} file")
    if not problems:
        return None
    return "This release can't be published yet: " + "; ".join(problems) + "."


def release_transition_blocker(release, target, user):
    """Why `user` can't move `release` to `target`, or None (permission to try is checked by the view)."""
    if target not in RELEASE_TRANSITIONS.get(release.status, set()):
        return f"A release can't move from {release.status} to {target}."
    # Two-person rule, creator half, as for datasets; the approver may publish for now (#131).
    if target == ReleaseStatus.APPROVED and release.created_by_id == user.id:
        return "You created this release, so another editor has to approve it."
    if target == ReleaseStatus.PUBLISHED:
        return release_publish_blocker(release)
    return None


def publish(release, metadata_serializer):
    """Make the release the dataset's live version, in one transaction. `metadata_serializer` is the release's metadata
    already validated against the dataset (ReleaseMetadataSerializer)."""
    dataset = metadata_serializer.instance  # the same object the metadata is applied to, so save() keeps it
    with transaction.atomic():
        metadata_serializer.save()
        main = release.main_file
        old_extras = list(dataset.extra_files.all())
        dataset.file.name = main.file.name
        dataset.format = release.format
        dataset.version = release.version
        dataset.save()  # a new file name makes save() work out the row count, columns and size again
        for extra in old_extras:
            extra.delete()  # the stored files stay: the previous release still points at them
        for f in release.files.all():
            if f.format != release.format:
                DatasetFile.objects.create(dataset=dataset, format=f.format, file=f.file.name, size=f.size)
        release.status = ReleaseStatus.PUBLISHED
        release.published_at = timezone.now()
        release.save(update_fields=["status", "published_at", "updated_at"])
    return release
