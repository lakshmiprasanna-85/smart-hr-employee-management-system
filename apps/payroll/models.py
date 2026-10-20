from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class PayrollPeriod(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="uniq_payroll_period_year_month"),
        ]

    @property
    def label(self):
        return f"{self.year}-{self.month:02d}"

    def __str__(self):
        return self.label


class SalaryComponent(models.Model):
    """Catalogue of pay items, e.g. Basic, HRA (earnings) and PF, Tax (deductions)."""

    class ComponentType(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    class CalculationType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENT_OF_BASIC = "percent_of_basic", "Percent of basic"

    name = models.CharField(max_length=60, unique=True)
    component_type = models.CharField(max_length=10, choices=ComponentType.choices)
    calculation_type = models.CharField(
        max_length=20, choices=CalculationType.choices, default=CalculationType.FIXED
    )
    default_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["component_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.component_type})"


class EmployeeSalaryComponent(models.Model):
    """The value of a salary component for one employee."""

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="salary_components",
    )
    component = models.ForeignKey(
        SalaryComponent, on_delete=models.PROTECT, related_name="employee_values"
    )
    value = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "component"], name="uniq_employee_salary_component"
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} {self.component.name}: {self.value}"


class PayrollRecord(models.Model):
    """One payroll row per employee per period, plus payslip metadata."""

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        ON_HOLD = "on_hold", "On hold"

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.PROTECT, related_name="payroll_records"
    )
    period = models.ForeignKey(
        PayrollPeriod, on_delete=models.PROTECT, related_name="records"
    )
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    paid_on = models.DateField(null=True, blank=True)

    # Payslip metadata (the generator itself is built in Week 3)
    payslip_file = models.FileField(upload_to="payslips/", blank=True)
    payslip_generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period__year", "-period__month", "employee__employee_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "period"], name="uniq_payroll_employee_period"
            ),
            models.CheckConstraint(
                condition=Q(gross_amount__gte=0) & Q(total_deductions__gte=0),
                name="payroll_amounts_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} {self.period} net={self.net_amount}"
