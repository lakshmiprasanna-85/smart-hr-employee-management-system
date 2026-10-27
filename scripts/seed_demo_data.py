"""
Create synthetic demo data: one login per role, departments, employee profiles,
leave types, salary components and two payroll periods with payslips. Safe to run
more than once (it never creates duplicates).

Run from the project root:

    python scripts/seed_demo_data.py

Names are the project team; e-mail addresses are placeholders (example.com). The password for
every demo account comes from SEED_PASSWORD in your .env file.
"""
import os
import sys
from datetime import date
from pathlib import Path

# Make the project root importable and start Django.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.accounts.models import User  # noqa: E402
from apps.employees.models import Department, Employee  # noqa: E402
from apps.leave_management.models import LeaveType  # noqa: E402
from apps.payroll.models import EmployeeSalaryComponent, PayrollPeriod, PayrollRecord, SalaryComponent  # noqa: E402
from apps.payroll.payslips import generate_payslips_for_period  # noqa: E402
from apps.payroll.services import close_period, create_period, generate_payroll, set_payment_status  # noqa: E402

PASSWORD = os.environ.get("SEED_PASSWORD", "Demo@12345")

DEPARTMENTS = {
    "Engineering": "Builds and maintains the product.",
    "Human Resources": "People operations and recruitment.",
    "Finance": "Payroll, budgets and accounting.",
}

LEAVE_TYPES = [
    # (name, annual quota in days, paid?)
    ("Casual Leave", 12, True),
    ("Sick Leave", 10, True),
    ("Earned Leave", 15, True),
    ("Unpaid Leave", 0, False),
]

# (username, first name, last name, role, employee code, department, job title, joining date)
PEOPLE = [
    ("admin_demo", "Lakshmi", "Prasanna", User.Role.ADMIN, "EMP001", "Human Resources", "System Administrator", date(2023, 4, 3)),
    ("hr_demo", "Abhinav", "Shukla", User.Role.HR, "EMP002", "Human Resources", "HR Manager", date(2023, 6, 12)),
    ("employee_demo", "Subhankar", "Khatua", User.Role.EMPLOYEE, "EMP003", "Engineering", "Software Engineer", date(2024, 1, 15)),
    ("employee_demo2", "Prajwal", "Nitin", User.Role.EMPLOYEE, "EMP004", "Finance", "Accountant", date(2024, 8, 5)),
]


EARNING, DEDUCTION = SalaryComponent.ComponentType.EARNING, SalaryComponent.ComponentType.DEDUCTION
FIXED, PERCENT = SalaryComponent.CalculationType.FIXED, SalaryComponent.CalculationType.PERCENT_OF_BASIC

# (name, type, calculation, default). A PERCENT value is a percentage of Basic.
SALARY_COMPONENTS = [
    ("Basic", EARNING, FIXED, 0),
    ("HRA", EARNING, PERCENT, 40),
    ("Special Allowance", EARNING, FIXED, 0),
    ("Provident Fund", DEDUCTION, PERCENT, 12),
    ("Professional Tax", DEDUCTION, FIXED, 200),
]

# employee code -> (basic, special allowance). All figures are made up.
SALARIES = {
    "EMP001": (90000, 10000),
    "EMP002": (75000, 8000),
    "EMP003": (60000, 6000),
    "EMP004": (50000, 5000),
}

# (year, month, mark everything paid and close it?)
PAYROLL_PERIODS = [(2026, 8, True), (2026, 9, False)]


def seed_payroll():
    components = {}
    for name, kind, calc, default in SALARY_COMPONENTS:
        components[name], _ = SalaryComponent.objects.get_or_create(
            name=name,
            defaults={"component_type": kind, "calculation_type": calc, "default_value": default},
        )

    for code, (basic, special) in SALARIES.items():
        employee = Employee.objects.get(employee_code=code)
        values = {
            "Basic": basic,
            "HRA": components["HRA"].default_value,
            "Special Allowance": special,
            "Provident Fund": components["Provident Fund"].default_value,
            "Professional Tax": components["Professional Tax"].default_value,
        }
        for name, value in values.items():
            EmployeeSalaryComponent.objects.get_or_create(
                employee=employee, component=components[name], defaults={"value": value}
            )

    for year, month, finished in PAYROLL_PERIODS:
        period = PayrollPeriod.objects.filter(year=year, month=month).first() or create_period(year, month)
        if period.status == PayrollPeriod.Status.CLOSED:
            continue
        generate_payroll(period)
        generate_payslips_for_period(period, notify=False)  # no emails while seeding
        if finished:
            for record in period.records.filter(payment_status=PayrollRecord.PaymentStatus.PENDING):
                set_payment_status(record, PayrollRecord.PaymentStatus.PAID)
            close_period(period)
        print(f"payroll {period.label}: {period.records.count()} records, status={period.status}")


def main():
    for name, description in DEPARTMENTS.items():
        Department.objects.get_or_create(name=name, defaults={"description": description})

    for name, quota, is_paid in LEAVE_TYPES:
        LeaveType.objects.get_or_create(
            name=name, defaults={"annual_quota_days": quota, "is_paid": is_paid}
        )

    for username, first, last, role, code, dept, title, joined in PEOPLE:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first,
                "last_name": last,
                "email": f"{username}@example.com",
                "role": role,
                # Only the Admin may open the Django admin site (/admin/).
                "is_staff": role == User.Role.ADMIN,
                "is_superuser": role == User.Role.ADMIN,
            },
        )
        if created:
            user.set_password(PASSWORD)
            user.save()
        elif (user.first_name, user.last_name) != (first, last):
            # Keep demo names in sync if they were changed in this script.
            user.first_name, user.last_name = first, last
            user.save(update_fields=["first_name", "last_name"])
        Employee.objects.get_or_create(
            user=user,
            defaults={
                "employee_code": code,
                "department": Department.objects.get(name=dept),
                "job_title": title,
                "joining_date": joined,
            },
        )
        print(f"{'created' if created else 'exists '}  {username:<15} role={role}")

    seed_payroll()

    print(f"\nDemo password for newly created accounts: {PASSWORD}")


if __name__ == "__main__":
    main()
