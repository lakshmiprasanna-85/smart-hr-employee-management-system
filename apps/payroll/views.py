from django.shortcuts import render
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User
from apps.accounts.permissions import role_required

from .models import PayrollPeriod, PayrollRecord
from .serializers import PayrollRecordSerializer


@role_required(User.Role.ADMIN, User.Role.HR)
def payroll_home(request):
    """Payroll management shell: Admin and HR only (employees get 403)."""
    periods = PayrollPeriod.objects.all()[:12]
    return render(request, "payroll/index.html", {"periods": periods})


class PayrollRecordListView(ListAPIView):
    """
    Payroll records.

    Admin/HR see every record. An employee sees only their own records.
    Anonymous users are rejected by IsAuthenticated.
    """

    serializer_class = PayrollRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PayrollRecord.objects.select_related("employee", "period")
        user = self.request.user
        if user.role in (User.Role.ADMIN, User.Role.HR):
            return queryset
        return queryset.filter(employee__user=user)
