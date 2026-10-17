from django.contrib import admin

from .models import LeaveRequest, LeaveStatusHistory, LeaveType


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "annual_quota_days", "is_paid", "is_active")


class LeaveStatusHistoryInline(admin.TabularInline):
    model = LeaveStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "note", "changed_at")
    can_delete = False


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")
    inlines = [LeaveStatusHistoryInline]
