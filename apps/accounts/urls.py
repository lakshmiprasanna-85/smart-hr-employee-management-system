from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="dashboard-admin"),
    path("dashboard/hr/", views.hr_dashboard, name="dashboard-hr"),
    path("dashboard/employee/", views.employee_dashboard, name="dashboard-employee"),
]
