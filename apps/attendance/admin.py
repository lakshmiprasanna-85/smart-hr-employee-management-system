from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "status", "check_in", "check_out", "is_corrected")
    list_filter = ("status", "date")
    search_fields = ("employee__employee_code", "employee__user__username")
