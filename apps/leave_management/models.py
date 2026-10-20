from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .states import LeaveStatus


class LeaveType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    annual_quota_days = models.PositiveIntegerField(default=0)
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="requests"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=LeaveStatus.choices, default=LeaveStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_leave_requests",
    )
    reviewer_note = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="leave_end_not_before_start",
            ),
        ]

    @property
    def total_days(self):
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.employee.employee_code} {self.leave_type} {self.start_date}..{self.end_date} [{self.status}]"


class LeaveStatusHistory(models.Model):
    """Every status change of a leave request is recorded here."""

    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="history"
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, choices=LeaveStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    note = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at"]
        verbose_name_plural = "leave status history"

    def __str__(self):
        return f"{self.leave_request_id}: {self.from_status or '-'} -> {self.to_status}"
