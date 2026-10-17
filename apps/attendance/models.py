from django.db import models
from django.db.models import F, Q


class Attendance(models.Model):
    """One attendance record per employee per day."""

    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        HALF_DAY = "half_day", "Half day"
        ON_LEAVE = "on_leave", "On leave"

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    notes = models.TextField(blank=True)
    is_corrected = models.BooleanField(
        default=False, help_text="True when HR/Admin corrected this record after entry."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="uniq_attendance_employee_date"
            ),
            models.CheckConstraint(
                condition=(
                    Q(check_in__isnull=True)
                    | Q(check_out__isnull=True)
                    | Q(check_out__gt=F("check_in"))
                ),
                name="attendance_checkout_after_checkin",
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} {self.date} {self.status}"
