"""Web pages for attendance. The rules live in services.py; these views only call them."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.employees.models import Employee

from .models import Attendance
from .services import AttendanceError, check_in, check_out, monthly_summary


@login_required
def my_attendance(request):
    """Check in/out and the last 31 days of the logged-in person's own attendance."""
    profile = getattr(request.user, "employee_profile", None)
    today = timezone.localdate()
    records, today_record = [], None
    if profile is not None:
        records = Attendance.objects.filter(
            employee=profile, date__gte=today - timedelta(days=31)
        )
        today_record = next((r for r in records if r.date == today), None)
    return render(
        request,
        "attendance/index.html",
        {"profile": profile, "records": records, "today": today, "today_record": today_record},
    )


def _run(request, action, done):
    try:
        action(request.user)
    except AttendanceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, done)
    return redirect("attendance-home")


@login_required
@require_POST
def check_in_page(request):
    return _run(request, check_in, "Checked in.")


@login_required
@require_POST
def check_out_page(request):
    return _run(request, check_out, "Checked out.")


def _int(value, default, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if low <= number <= high else default


@role_required(User.Role.ADMIN, User.Role.HR)
def team_attendance(request):
    """Who is in today, plus the monthly totals per employee (Admin/HR only)."""
    today = timezone.localdate()
    year = _int(request.GET.get("year"), today.year, 2000, 2100)
    month = _int(request.GET.get("month"), today.month, 1, 12)

    todays = {r.employee_id: r for r in Attendance.objects.filter(date=today)}
    people = Employee.objects.exclude(employment_status=Employee.Status.TERMINATED).select_related("user")
    board = [{"employee": e, "record": todays.get(e.pk)} for e in people]

    return render(
        request,
        "attendance/team.html",
        {
            "today": today,
            "board": board,
            "summary": monthly_summary(year, month),
            "year": year,
            "month": month,
            "months": [(n, name) for n, name in enumerate(
                ["January", "February", "March", "April", "May", "June", "July",
                 "August", "September", "October", "November", "December"], start=1)],
        },
    )
