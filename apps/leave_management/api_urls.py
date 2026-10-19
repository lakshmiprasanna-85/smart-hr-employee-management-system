from django.urls import path

from .views import (
    LeaveRequestDecisionView,
    LeaveRequestHistoryView,
    LeaveRequestListCreateView,
)

urlpatterns = [
    path("requests/", LeaveRequestListCreateView.as_view(), name="api-leave-requests"),
    path(
        "requests/<int:pk>/decide/",
        LeaveRequestDecisionView.as_view(),
        name="api-leave-decide",
    ),
    path(
        "requests/<int:pk>/history/",
        LeaveRequestHistoryView.as_view(),
        name="api-leave-history",
    ),
]
