from django.urls import path

from . import views

urlpatterns = [
    path("", views.payroll_home, name="payroll-home"),
    path("my/", views.my_payslips, name="payroll-my"),
    path("periods/<int:pk>/", views.period_detail, name="payroll-period"),
    path("periods/<int:pk>/generate/", views.period_generate, name="payroll-period-generate"),
    path("periods/<int:pk>/payslips/", views.period_payslips, name="payroll-period-payslips"),
    path("periods/<int:pk>/close/", views.period_close, name="payroll-period-close"),
    path("records/<int:pk>/status/", views.record_status, name="payroll-record-status"),
    path("records/<int:pk>/payslip/", views.record_payslip, name="payroll-record-payslip"),
    path("payslips/<int:pk>/download/", views.payslip_download, name="payslip-download"),
]
