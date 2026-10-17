from django.urls import path

from .views import (
    AttendanceRecordListView,
    AttendanceSummaryView,
    CheckInView,
    CheckOutView,
)

urlpatterns = [
    path("checkin/", CheckInView.as_view(), name="api-attendance-checkin"),
    path("checkout/", CheckOutView.as_view(), name="api-attendance-checkout"),
    path("records/", AttendanceRecordListView.as_view(), name="api-attendance-records"),
    path("summary/", AttendanceSummaryView.as_view(), name="api-attendance-summary"),
]
