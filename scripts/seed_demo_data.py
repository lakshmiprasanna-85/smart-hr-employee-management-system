"""
Create synthetic demo data: one login per role, departments, employee profiles
and leave types. Safe to run more than once (it never creates duplicates).

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

    print(f"\nDemo password for newly created accounts: {PASSWORD}")


if __name__ == "__main__":
    main()
