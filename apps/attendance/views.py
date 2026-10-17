from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsHROrAdmin

from .models import Attendance
from .serializers import AttendanceSerializer
from .services import AttendanceError, check_in, check_out, monthly_summary


class CheckInView(APIView):
    """Employees record their own check-in for the current day."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            record = check_in(request.user)
        except AttendanceError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(AttendanceSerializer(record).data, status=201)


class CheckOutView(APIView):
    """Employees close their own check-in for the current day."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            record = check_out(request.user)
        except AttendanceError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(AttendanceSerializer(record).data)


class AttendanceRecordListView(ListAPIView):
    """Admin/HR see every record; an employee sees only their own."""

    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Attendance.objects.select_related("employee")
        user = self.request.user
        if user.role in (User.Role.ADMIN, User.Role.HR):
            employee = self.request.query_params.get("employee")
            if employee:
                queryset = queryset.filter(employee_id=employee)
            return queryset
        return queryset.filter(employee__user=user)


class AttendanceSummaryView(APIView):
    """Monthly attendance totals per employee. Admin/HR only."""

    permission_classes = [IsHROrAdmin]

    def get(self, request):
        now = timezone.now()
        try:
            year = int(request.query_params.get("year", now.year))
            month = int(request.query_params.get("month", now.month))
        except (TypeError, ValueError):
            return Response({"detail": "year and month must be integers."}, status=400)
        if not 1 <= month <= 12:
            return Response({"detail": "month must be between 1 and 12."}, status=400)
        return Response(
            {"year": year, "month": month, "rows": monthly_summary(year, month)}
        )
