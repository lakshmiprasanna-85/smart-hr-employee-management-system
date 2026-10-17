from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.api_urls")),
    path("api/payroll/", include("apps.payroll.api_urls")),
    path("payroll/", include("apps.payroll.urls")),
    path("", include("apps.accounts.urls")),
]
