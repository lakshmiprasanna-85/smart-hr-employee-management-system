"""Payroll business rules: salary calculation, payroll generation and payment status."""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.employees.models import Employee
from apps.reports.models import AuditEvent
from apps.reports.services import record_event

from .models import PayrollPeriod, PayrollRecord, PayrollRecordLine, SalaryComponent

TWO_PLACES = Decimal("0.01")
BASIC_NAME = "basic"  # the component that PERCENT_OF_BASIC items are calculated from

Status = PayrollRecord.PaymentStatus

# Allowed payment-status moves. PAID is final.
PAYMENT_TRANSITIONS = {
    Status.PENDING: {Status.PAID, Status.ON_HOLD},
    Status.ON_HOLD: {Status.PENDING, Status.PAID},
    Status.PAID: set(),
}


class PayrollError(Exception):
    """Raised when a payroll rule is broken (closed period, bad transition, ...)."""


def money(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# Periods
# --------------------------------------------------------------------------
def create_period(year, month, actor=None):
    """Create the payroll period for a calendar month (start and end dates are derived)."""
    if not 1 <= month <= 12:
        raise PayrollError("Month must be between 1 and 12.")
    if PayrollPeriod.objects.filter(year=year, month=month).exists():
        raise PayrollError(f"A payroll period for {year}-{month:02d} already exists.")
    last_day = calendar.monthrange(year, month)[1]
    period = PayrollPeriod.objects.create(
        year=year,
        month=month,
        start_date=date(year, month, 1),
        end_date=date(year, month, last_day),
    )
    record_event(actor, AuditEvent.Action.CREATE, "PayrollPeriod", period.pk, {"period": period.label})
    return period


@transaction.atomic
def close_period(period, actor=None):
    """Close a period. Not allowed while any record is still pending payment."""
    if period.status == PayrollPeriod.Status.CLOSED:
        raise PayrollError("This payroll period is already closed.")
    pending = period.records.filter(payment_status=Status.PENDING).count()
    if pending:
        raise PayrollError(f"{pending} payroll record(s) are still pending. Mark them paid or on hold first.")
    period.status = PayrollPeriod.Status.CLOSED
    period.save(update_fields=["status"])
    record_event(
        actor,
        AuditEvent.Action.STATUS_CHANGE,
        "PayrollPeriod",
        period.pk,
        {"period": period.label, "from": "open", "to": "closed"},
    )
    return period


# --------------------------------------------------------------------------
# Calculation
# --------------------------------------------------------------------------
def calculate_salary(employee):
    """
    Work out one employee's pay from their salary components.

    Returns a list of (name, component_type, amount) lines.

    * FIXED components: the stored value is the amount.
    * PERCENT_OF_BASIC components: the stored value is a percentage (0-100) of the
      employee's "Basic" earning.

    Raises PayrollError if there is nothing to pay, a percent item has no Basic to
    work from, or the deductions are larger than the earnings.
    """
    rows = list(
        employee.salary_components.select_related("component").filter(component__is_active=True)
    )
    if not rows:
        raise PayrollError("No active salary components.")

    basic = next(
        (
            row.value
            for row in rows
            if row.component.name.strip().lower() == BASIC_NAME
            and row.component.component_type == SalaryComponent.ComponentType.EARNING
        ),
        None,
    )

    lines = []
    for row in rows:
        comp = row.component
        if comp.calculation_type == SalaryComponent.CalculationType.PERCENT_OF_BASIC:
            if basic is None:
                raise PayrollError(f"'{comp.name}' is a percent of Basic, but there is no Basic component.")
            amount = money(basic * row.value / 100)
        else:
            amount = money(row.value)
        lines.append((comp.name, comp.component_type, amount))

    earnings = sum((a for _, t, a in lines if t == SalaryComponent.ComponentType.EARNING), Decimal("0"))
    deductions = sum((a for _, t, a in lines if t == SalaryComponent.ComponentType.DEDUCTION), Decimal("0"))
    if earnings <= 0:
        raise PayrollError("Earnings must be greater than zero.")
    if deductions > earnings:
        raise PayrollError("Deductions are larger than earnings.")
    return lines


def _totals(lines):
    gross = sum((a for _, t, a in lines if t == SalaryComponent.ComponentType.EARNING), Decimal("0"))
    deductions = sum((a for _, t, a in lines if t == SalaryComponent.ComponentType.DEDUCTION), Decimal("0"))
    return money(gross), money(deductions), money(gross - deductions)


def _clear_payslip(record):
    """Forget a stored payslip so it is regenerated from the new figures."""
    if record.payslip_file:
        record.payslip_file.delete(save=False)
    record.payslip_file = ""
    record.payslip_generated_at = None


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------
def generate_payroll(period, actor=None):
    """
    Create or refresh the payroll records of every working employee for a period.

    * Closed periods cannot be changed.
    * Records that are already PAID are never touched.
    * If figures change on an unpaid record, its old payslip is discarded.
    * Employees that cannot be calculated are reported, not silently skipped.

    Returns {"created": n, "updated": n, "unchanged": n, "skipped_paid": n, "errors": [(code, reason)]}.
    """
    if period.status == PayrollPeriod.Status.CLOSED:
        raise PayrollError("This payroll period is closed.")

    summary = {"created": 0, "updated": 0, "unchanged": 0, "skipped_paid": 0, "errors": []}
    employees = Employee.objects.exclude(employment_status=Employee.Status.TERMINATED).filter(
        joining_date__lte=period.end_date
    )
    for employee in employees:
        existing = PayrollRecord.objects.filter(employee=employee, period=period).first()
        if existing and existing.payment_status == Status.PAID:
            summary["skipped_paid"] += 1
            continue
        try:
            lines = calculate_salary(employee)
        except PayrollError as exc:
            if employee.salary_components.exists() or existing:
                summary["errors"].append((employee.employee_code, str(exc)))
            continue  # employees with no salary set up at all are simply not on payroll
        gross, deductions, net = _totals(lines)

        with transaction.atomic():
            if existing is None:
                record = PayrollRecord.objects.create(
                    employee=employee,
                    period=period,
                    gross_amount=gross,
                    total_deductions=deductions,
                    net_amount=net,
                )
                _save_lines(record, lines)
                summary["created"] += 1
                record_event(
                    actor,
                    AuditEvent.Action.CREATE,
                    "PayrollRecord",
                    record.pk,
                    {"employee": employee.employee_code, "period": period.label, "net": str(net)},
                )
            elif (existing.gross_amount, existing.total_deductions, existing.net_amount) == (gross, deductions, net):
                summary["unchanged"] += 1
            else:
                before = str(existing.net_amount)
                existing.gross_amount, existing.total_deductions, existing.net_amount = gross, deductions, net
                _clear_payslip(existing)
                existing.save()
                _save_lines(existing, lines)
                summary["updated"] += 1
                record_event(
                    actor,
                    AuditEvent.Action.UPDATE,
                    "PayrollRecord",
                    existing.pk,
                    {"employee": employee.employee_code, "period": period.label, "net_before": before, "net_after": str(net)},
                )
    return summary


def _save_lines(record, lines):
    record.lines.all().delete()
    PayrollRecordLine.objects.bulk_create(
        [PayrollRecordLine(record=record, name=n, component_type=t, amount=a) for n, t, a in lines]
    )


# --------------------------------------------------------------------------
# Payment status
# --------------------------------------------------------------------------
@transaction.atomic
def set_payment_status(record, to_status, actor=None, paid_on=None):
    """Move a record to a new payment status, following PAYMENT_TRANSITIONS."""
    if to_status not in PAYMENT_TRANSITIONS.get(record.payment_status, set()):
        raise PayrollError(f"Cannot move a {record.payment_status} payroll record to {to_status}.")
    from_status = record.payment_status
    record.payment_status = to_status
    record.paid_on = (paid_on or timezone.localdate()) if to_status == Status.PAID else None
    record.save(update_fields=["payment_status", "paid_on", "updated_at"])
    record_event(
        actor,
        AuditEvent.Action.STATUS_CHANGE,
        "PayrollRecord",
        record.pk,
        {"employee": record.employee.employee_code, "period": record.period.label, "from": from_status, "to": to_status},
    )
    return record
