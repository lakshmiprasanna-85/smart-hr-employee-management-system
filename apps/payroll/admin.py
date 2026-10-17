from django.contrib import admin

from .models import EmployeeSalaryComponent, PayrollPeriod, PayrollRecord, SalaryComponent


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("label", "start_date", "end_date", "status")


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "component_type", "calculation_type", "default_value", "is_active")


@admin.register(EmployeeSalaryComponent)
class EmployeeSalaryComponentAdmin(admin.ModelAdmin):
    list_display = ("employee", "component", "value")


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "period", "gross_amount", "total_deductions", "net_amount", "payment_status")
    list_filter = ("period", "payment_status")
