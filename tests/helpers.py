"""Small helpers for creating test data."""
from datetime import date
from decimal import Decimal

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.leave_management.models import LeaveType
from apps.payroll.models import PayrollPeriod, PayrollRecord

PASSWORD = "Test@12345"


def make_user(username, role=User.Role.EMPLOYEE):
    return User.objects.create_user(
        username=username, password=PASSWORD, email=f"{username}@example.com", role=role
    )


def make_employee(user, code, joining=date(2025, 1, 6)):
    return Employee.objects.create(user=user, employee_code=code, joining_date=joining)


def make_period(year=2026, month=9):
    return PayrollPeriod.objects.create(
        year=year, month=month, start_date=date(year, month, 1), end_date=date(year, month, 28)
    )


def make_payroll(employee, period, gross="50000.00", deductions="5000.00"):
    gross, deductions = Decimal(gross), Decimal(deductions)
    return PayrollRecord.objects.create(
        employee=employee,
        period=period,
        gross_amount=gross,
        total_deductions=deductions,
        net_amount=gross - deductions,
    )


def make_leave_type(name="Casual Leave", quota=12):
    return LeaveType.objects.create(name=name, annual_quota_days=quota)
