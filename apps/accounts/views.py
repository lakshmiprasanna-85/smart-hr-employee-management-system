from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import role_required

ROLE_DASHBOARD = {
    User.Role.ADMIN: "dashboard-admin",
    User.Role.HR: "dashboard-hr",
    User.Role.EMPLOYEE: "dashboard-employee",
}


def home(request):
    return redirect("dashboard")


@login_required
def dashboard_redirect(request):
    """Send each user to the dashboard that matches their role."""
    return redirect(ROLE_DASHBOARD.get(request.user.role, "dashboard-employee"))


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    return render(request, "dashboards/admin.html")


@role_required(User.Role.ADMIN, User.Role.HR)
def hr_dashboard(request):
    return render(request, "dashboards/hr.html")


@role_required(User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE)
def employee_dashboard(request):
    profile = getattr(request.user, "employee_profile", None)
    return render(request, "dashboards/employee.html", {"profile": profile})


class MeView(APIView):
    """Returns the logged-in user's basic identity and role."""

    def get(self, request):
        user = request.user
        return Response(
            {"username": user.username, "email": user.email, "role": user.role}
        )
