"""Read-only aggregations for the Week 4 reports page.

The page and the downloadable reports both use these helpers, so every KPI is
defined in one place. Each KPI is documented in the README ("KPI definitions").
"""
import calendar
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.attendance.models import Attendance
from apps.employees.models import Employee
from apps.leave_management.models import LeaveRequest
from apps.leave_management.states import LeaveStatus
from apps.payroll.models import PayrollPeriod, PayrollRecord

MONTHS = [(number, calendar.month_name[number]) for number in range(1, 13)]
PAYROLL_TREND_PERIODS = 6


def int_in_range(value, default, low, high):
    """Parse a query-string number, falling back to `default` when it is invalid."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


def year_month(raw_year, raw_month):
    """The report month, defaulting to today when the parameters are missing or invalid."""
    today = timezone.localdate()
    return (
        int_in_range(raw_year, today.year, 2000, 2100),
        int_in_range(raw_month, today.month, 1, 12),
    )


def month_label(year, month):
    return f"{calendar.month_name[month]} {year}"


def _with_shares(rows):
    """Add a whole-number percentage to each row and return (rows, total)."""
    total = sum(row["count"] for row in rows)
    for row in rows:
        row["percent"] = round(row["count"] * 100 / total) if total else 0
    return rows, total


def headcount_by_department():
    """Employees who are not terminated, grouped by department."""
    raw = (
        Employee.objects.exclude(employment_status=Employee.Status.TERMINATED)
        .values("department__name")
        .annotate(count=Count("id"))
        .order_by()
    )
    rows = [
        {"label": row["department__name"] or "No department", "count": row["count"]}
        for row in raw
    ]
    rows.sort(key=lambda row: (-row["count"], row["label"]))
    rows, total = _with_shares(rows)
    return {"rows": rows, "total": total}


def attendance_mix(year, month):
    """Attendance records in a calendar month, counted by status."""
    counts = {value: 0 for value, _ in Attendance.Status.choices}
    for row in (
        Attendance.objects.filter(date__year=year, date__month=month)
        .values("status")
        .annotate(count=Count("id"))
    ):
        counts[row["status"]] = row["count"]

    rows = [
        {"status": value, "label": label, "count": counts[value]}
        for value, label in Attendance.Status.choices
    ]
    rows, total = _with_shares(rows)
    return {
        "rows": rows,
        "total": total,
        "segments": [row for row in rows if row["count"]],
    }


def leave_mix(year, month):
    """Leave requests starting in a calendar month, counted by status."""
    counts = {value: 0 for value, _ in LeaveStatus.choices}
    for row in (
        LeaveRequest.objects.filter(start_date__year=year, start_date__month=month)
        .values("status")
        .annotate(count=Count("id"))
    ):
        counts[row["status"]] = row["count"]

    rows = [
        {"status": value, "label": label, "count": counts[value]}
        for value, label in LeaveStatus.choices
    ]
    rows, total = _with_shares(rows)
    return {"rows": rows, "total": total}


def payroll_trend(limit=PAYROLL_TREND_PERIODS):
    """Net payroll totals for the most recent periods, oldest first."""
    periods = list(PayrollPeriod.objects.order_by("-year", "-month")[:limit])[::-1]
    totals = {
        row["period_id"]: row["net"] or Decimal("0")
        for row in PayrollRecord.objects.filter(period__in=periods)
        .values("period_id")
        .annotate(net=Sum("net_amount"))
    }
    rows = [
        {"period": period, "label": period.label, "value": totals.get(period.pk, Decimal("0"))}
        for period in periods
    ]
    largest = max((row["value"] for row in rows), default=Decimal("0"))
    for row in rows:
        row["percent"] = round(float(row["value"]) * 100 / float(largest)) if largest else 0
    latest = periods[-1] if periods else None
    return {
        "rows": rows,
        "latest_period": latest,
        "latest_total": totals.get(latest.pk, Decimal("0")) if latest else Decimal("0"),
    }


def overview(year, month):
    """Every number the reports page needs for one month."""
    today = timezone.localdate()
    headcount = (
        Employee.objects.exclude(employment_status=Employee.Status.TERMINATED).count()
    )
    present_today = (
        Attendance.objects.filter(date=today, check_in__isnull=False)
        .exclude(employee__employment_status=Employee.Status.TERMINATED)
        .count()
    )
    pending_leave = LeaveRequest.objects.filter(status=LeaveStatus.PENDING).count()
    trend = payroll_trend()
    return {
        "headcount": headcount,
        "present_today": present_today,
        "pending_leave": pending_leave,
        "latest_period": trend["latest_period"],
        "latest_net": trend["latest_total"],
        "by_department": headcount_by_department(),
        "attendance": attendance_mix(year, month),
        "leave": leave_mix(year, month),
        "payroll": trend,
    }
