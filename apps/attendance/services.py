"""Attendance business rules, kept out of the views so they are easy to test."""
from django.db import transaction
from django.utils import timezone

from .models import Attendance


class AttendanceError(Exception):
    """Raised when a check-in or check-out is not allowed."""


def _profile_or_error(user):
    profile = getattr(user, "employee_profile", None)
    if profile is None:
        raise AttendanceError("This account has no employee profile.")
    return profile


def _local_date(at):
    return timezone.localtime(at).date()


@transaction.atomic
def check_in(user, at=None):
    """Record a check-in for today. One record per employee per day."""
    profile = _profile_or_error(user)
    at = at or timezone.now()
    record, created = Attendance.objects.get_or_create(
        employee=profile, date=_local_date(at), defaults={"check_in": at}
    )
    if not created:
        if record.check_in is not None:
            raise AttendanceError("Already checked in for today.")
        record.check_in = at
        record.save(update_fields=["check_in", "updated_at"])
    return record


@transaction.atomic
def check_out(user, at=None):
    """Close today's record. Requires an open check-in."""
    profile = _profile_or_error(user)
    at = at or timezone.now()
    record = Attendance.objects.filter(employee=profile, date=_local_date(at)).first()
    if record is None or record.check_in is None:
        raise AttendanceError("No open check-in for today.")
    if record.check_out is not None:
        raise AttendanceError("Already checked out for today.")
    if at <= record.check_in:
        raise AttendanceError("Check-out must be after check-in.")
    record.check_out = at
    record.save(update_fields=["check_out", "updated_at"])
    return record


def monthly_summary(year, month):
    """
    Per-employee attendance totals for a calendar month.

    Returns a list of rows: employee code, label and a count per status.
    """
    records = Attendance.objects.filter(date__year=year, date__month=month).select_related(
        "employee", "employee__user"
    )

    summary = {}
    for record in records:
        row = summary.setdefault(
            record.employee_id,
            {
                "employee_code": record.employee.employee_code,
                "employee": str(record.employee),
                "days": 0,
                "present": 0,
                "absent": 0,
                "late": 0,
                "half_day": 0,
                "on_leave": 0,
            },
        )
        row["days"] += 1
        row[record.status] += 1
    return sorted(summary.values(), key=lambda row: row["employee_code"])
