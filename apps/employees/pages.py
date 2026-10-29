"""Read-only employee directory page for Admin/HR. Personal fields are not shown here."""
from django.db.models import Q
from django.shortcuts import render

from apps.accounts.models import User
from apps.accounts.permissions import role_required

from .models import Department, Employee


@role_required(User.Role.ADMIN, User.Role.HR)
def employee_directory(request):
    employees = Employee.objects.select_related("user", "department")
    query = request.GET.get("q", "").strip()
    department = request.GET.get("department", "")
    status = request.GET.get("status", "")
    if query:
        employees = employees.filter(
            Q(employee_code__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
        )
    if department.isdigit():
        employees = employees.filter(department_id=department)
    if status in Employee.Status.values:
        employees = employees.filter(employment_status=status)
    return render(
        request,
        "employees/directory.html",
        {
            "employees": employees,
            "departments": Department.objects.all(),
            "statuses": Employee.Status.choices,
            "q": query,
            "department": department,
            "status": status,
        },
    )
