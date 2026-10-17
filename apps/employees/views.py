from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsHROrAdmin

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeePublicSerializer,
    EmployeeSerializer,
)


class DepartmentListCreateView(ListCreateAPIView):
    """Departments: anyone logged in can read, only Admin/HR can create."""

    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsHROrAdmin()]


class EmployeeListCreateView(ListCreateAPIView):
    """
    Employee directory.

    Admin/HR get the full record (including personal fields) and may create
    employees. Everyone else gets the public directory view, read-only.
    """

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsHROrAdmin()]

    def get_serializer_class(self):
        user = self.request.user
        if self.request.method != "GET" or user.role in (User.Role.ADMIN, User.Role.HR):
            return EmployeeSerializer
        return EmployeePublicSerializer

    def get_queryset(self):
        queryset = Employee.objects.select_related("user", "department")
        department = self.request.query_params.get("department")
        status = self.request.query_params.get("status")
        search = self.request.query_params.get("q")
        if department:
            queryset = queryset.filter(department_id=department)
        if status:
            queryset = queryset.filter(employment_status=status)
        if search:
            queryset = queryset.filter(employee_code__icontains=search)
        return queryset


class EmployeeRetrieveUpdateView(RetrieveUpdateAPIView):
    """
    A single employee record.

    Admin/HR may read and update anyone. An employee may read (but not update)
    their own record; personal fields of other employees stay hidden.
    """

    queryset = Employee.objects.select_related("user", "department")

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsHROrAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        user = self.request.user
        if user.role in (User.Role.ADMIN, User.Role.HR):
            return EmployeeSerializer
        return EmployeePublicSerializer

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        is_privileged = user.role in (User.Role.ADMIN, User.Role.HR)
        if not is_privileged and obj.user_id != user.id:
            # Non-privileged users may only open their own record.
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return obj


class MyEmployeeView(APIView):
    """The logged-in employee's own profile, or 404-shaped empty for non-employees."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "employee_profile", None)
        if profile is None:
            return Response({"detail": "No employee profile for this account."}, status=404)
        return Response(EmployeeSerializer(profile).data)
