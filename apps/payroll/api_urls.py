from django.urls import path

from .views import PayrollRecordListView

urlpatterns = [
    path("records/", PayrollRecordListView.as_view(), name="api-payroll-records"),
]
