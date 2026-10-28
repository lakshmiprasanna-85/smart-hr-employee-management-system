from django.urls import path

from . import views

urlpatterns = [
    path("records/", views.PayrollRecordListView.as_view(), name="api-payroll-records"),
    path("records/<int:pk>/status/", views.PayrollRecordStatusView.as_view(), name="api-payroll-record-status"),
    path("periods/", views.PayrollPeriodListCreateView.as_view(), name="api-payroll-periods"),
    path("periods/<int:pk>/generate/", views.PeriodGenerateView.as_view(), name="api-payroll-generate"),
    path("periods/<int:pk>/payslips/", views.PeriodPayslipsView.as_view(), name="api-payroll-payslips"),
    path("periods/<int:pk>/close/", views.PeriodCloseView.as_view(), name="api-payroll-close"),
    path("components/", views.SalaryComponentListCreateView.as_view(), name="api-salary-components"),
    path("components/<int:pk>/", views.SalaryComponentDetailView.as_view(), name="api-salary-component"),
    path("employee-salary/", views.EmployeeSalaryListCreateView.as_view(), name="api-employee-salary"),
    path("employee-salary/<int:pk>/", views.EmployeeSalaryDetailView.as_view(), name="api-employee-salary-detail"),
]
