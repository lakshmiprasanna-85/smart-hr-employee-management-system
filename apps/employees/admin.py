from django.contrib import admin

from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "department", "job_title", "employment_status", "joining_date")
    list_filter = ("department", "employment_status")
    search_fields = ("employee_code", "user__username", "user__first_name", "user__last_name")
