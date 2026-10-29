from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.api_urls")),
    path("api/employees/", include("apps.employees.api_urls")),
    path("api/attendance/", include("apps.attendance.api_urls")),
    path("api/leave/", include("apps.leave_management.api_urls")),
    path("api/payroll/", include("apps.payroll.api_urls")),
    path("payroll/", include("apps.payroll.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("leave/", include("apps.leave_management.urls")),
    path("employees/", include("apps.employees.urls")),
    path("", include("apps.accounts.urls")),
]
