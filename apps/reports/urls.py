from django.urls import path

from . import pages

urlpatterns = [
    path("", pages.reports_home, name="reports-home"),
    path("export/<str:kind>/<str:fmt>/", pages.export_report, name="report-export"),
]
