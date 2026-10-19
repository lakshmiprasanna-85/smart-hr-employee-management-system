from django.urls import path

from .views import (
    DepartmentListCreateView,
    EmployeeListCreateView,
    EmployeeRetrieveUpdateView,
    MyEmployeeView,
)

urlpatterns = [
    path("departments/", DepartmentListCreateView.as_view(), name="api-departments"),
    path("employees/", EmployeeListCreateView.as_view(), name="api-employees"),
    path("employees/me/", MyEmployeeView.as_view(), name="api-employee-me"),
    path(
        "employees/<int:pk>/",
        EmployeeRetrieveUpdateView.as_view(),
        name="api-employee-detail",
    ),
]
