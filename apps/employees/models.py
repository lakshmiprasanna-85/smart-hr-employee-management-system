from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    """Employment record linked one-to-one with a login account."""

    class Status(models.TextChoices):
        PROBATION = "probation", "Probation"
        ACTIVE = "active", "Active"
        ON_LEAVE = "on_leave", "On leave"
        TERMINATED = "terminated", "Terminated"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
    )
    job_title = models.CharField(max_length=100, blank=True)
    employment_status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    joining_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)
    manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
    )

    # Personal information: visible only to Admin/HR and the employee themself.
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(exit_date__isnull=True) | Q(exit_date__gte=F("joining_date")),
                name="employee_exit_not_before_joining",
            ),
        ]

    def __str__(self):
        return f"{self.employee_code} - {self.user.get_full_name() or self.user.username}"
