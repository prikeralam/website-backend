"""Admin views over visitor accounts: sign-up and download figures, and the CSV export."""
import csv
import io
from datetime import timedelta

from django.db.models import Count, Min
from django.db.models.functions import Lower, TruncWeek
from django.utils import timezone

from apps.datarepo.models import DatasetDownload

from .models import Purpose, Role, User

WEEKS = 12


def visitor_stats(now=None):
    """Figures for the dashboard: visitor totals, weekly sign-ups (oldest first, empty weeks as 0), purposes, top
    organisations, and downloads (all accounts)."""
    now = now or timezone.now()
    visitors = User.objects.filter(role=Role.PUBLIC)
    # Weeks start on Monday in the site's own time zone, the same as the database's TruncWeek.
    local = timezone.localtime(now)
    this_week = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    first_week = this_week - timedelta(weeks=WEEKS - 1)
    counted = {
        row["week"].date(): row["n"]
        for row in visitors.filter(date_joined__gte=first_week)
        .annotate(week=TruncWeek("date_joined"))
        .values("week")
        .annotate(n=Count("id"))
    }
    weeks = [(first_week + timedelta(weeks=i)).date() for i in range(WEEKS)]
    weekly = [{"week": week.isoformat(), "count": counted.get(week, 0)} for week in weeks]
    labels = dict(Purpose.choices)
    purposes = [
        {"purpose": row["purpose"], "label": labels.get(row["purpose"], "Not given"), "count": row["n"]}
        for row in visitors.values("purpose").annotate(n=Count("id")).order_by("-n", "purpose")
    ]
    organisations = [
        {"organisation": row["shown"], "count": row["n"]}
        for row in visitors.exclude(organisation="")
        .annotate(name=Lower("organisation"))
        .values("name")
        # Grouped ignoring case; shown as a spelling visitors actually typed (capitalised ones sort first).
        .annotate(n=Count("id"), shown=Min("organisation"))
        .order_by("-n", "name")[:8]
    ]
    downloads = DatasetDownload.objects.all()
    top_datasets = [
        {"slug": row["dataset__slug"], "title": row["dataset__title"], "count": row["n"]}
        for row in downloads.values("dataset__slug", "dataset__title").annotate(n=Count("id")).order_by("-n")[:8]
    ]
    return {
        "visitors": {
            "total": visitors.count(),
            "confirmed": visitors.filter(email_verified=True).count(),
            "newsletter": visitors.filter(newsletter_opt_in=True).count(),
            "new_7_days": visitors.filter(date_joined__gte=now - timedelta(days=7)).count(),
            "new_30_days": visitors.filter(date_joined__gte=now - timedelta(days=30)).count(),
        },
        "weekly_signups": weekly,
        "purposes": purposes,
        "top_organisations": organisations,
        "downloads": {
            "total": downloads.count(),
            "last_30_days": downloads.filter(created_at__gte=now - timedelta(days=30)).count(),
            "top_datasets": top_datasets,
        },
    }


EXPORT_COLUMNS = [
    "Name", "Email", "Organisation", "Purpose", "Newsletter", "Email confirmed",
    "Role", "Active", "Joined", "Last sign-in", "Downloads",
]


def _cell(value):
    """A spreadsheet-safe cell: text that starts like a formula is prefixed so Excel shows it instead of running it."""
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def users_csv(users):
    """The given users as CSV text, one row each, with a UTF-8 marker so Excel reads names correctly."""
    labels = dict(Purpose.choices)
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for user in users.annotate(download_total=Count("dataset_downloads")):
        writer.writerow(
            [
                _cell(user.get_full_name() or user.username),
                _cell(user.email),
                _cell(user.organisation),
                _cell(labels.get(user.purpose, "")),
                "Yes" if user.newsletter_opt_in else "No",
                "Yes" if user.email_verified else "No",
                _cell(user.get_role_display()),
                "Yes" if user.is_active else "No",
                user.date_joined.date().isoformat(),
                user.last_login.date().isoformat() if user.last_login else "",
                user.download_total,
            ]
        )
    return buffer.getvalue()
