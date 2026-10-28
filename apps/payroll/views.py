import calendar
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import status as http
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsHROrAdmin, role_required
from apps.reports.models import AuditEvent
from apps.reports.services import record_event

from .models import EmployeeSalaryComponent, PayrollPeriod, PayrollRecord, SalaryComponent
from .payslips import generate_payslip, generate_payslips_for_period
from .serializers import (
    EmployeeSalaryComponentSerializer,
    PayrollPeriodSerializer,
    PayrollRecordSerializer,
    PayrollStatusSerializer,
    SalaryComponentSerializer,
    audit_salary_change,
)
from .services import (
    PayrollError,
    close_period,
    create_period,
    generate_payroll,
    set_payment_status,
)

logger = logging.getLogger(__name__)
PRIVILEGED = (User.Role.ADMIN, User.Role.HR)


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@role_required(*PRIVILEGED)
def payroll_home(request):
    """Payroll management: Admin and HR only (employees get 403)."""
    if request.method == "POST":
        try:
            period = create_period(int(request.POST.get("year", "")), int(request.POST.get("month", "")), request.user)
        except (ValueError, PayrollError) as exc:
            messages.error(request, str(exc) if isinstance(exc, PayrollError) else "Enter a valid year and month.")
        else:
            messages.success(request, f"Payroll period {period.label} created.")
            return redirect("payroll-period", pk=period.pk)
        return redirect("payroll-home")
    periods = PayrollPeriod.objects.all()[:24]
    months = [(n, calendar.month_name[n]) for n in range(1, 13)]
    return render(request, "payroll/index.html", {"periods": periods, "months": months})


@role_required(*PRIVILEGED)
def period_detail(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    records = period.records.select_related("employee__user", "employee__department")
    return render(request, "payroll/period.html", {"period": period, "records": records})


@role_required(*PRIVILEGED)
@require_POST
def period_generate(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    try:
        summary = generate_payroll(period, request.user)
    except PayrollError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Payroll generated: {summary['created']} new, {summary['updated']} updated, "
            f"{summary['unchanged']} unchanged, {summary['skipped_paid']} already paid.",
        )
        for code, reason in summary["errors"]:
            messages.error(request, f"{code}: {reason}")
    return redirect("payroll-period", pk=pk)


@role_required(*PRIVILEGED)
@require_POST
def period_payslips(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    count = generate_payslips_for_period(period, request.user)
    messages.success(request, f"{count} payslip(s) generated." if count else "Every record already has a payslip.")
    return redirect("payroll-period", pk=pk)


@role_required(*PRIVILEGED)
@require_POST
def period_close(request, pk):
    period = get_object_or_404(PayrollPeriod, pk=pk)
    try:
        close_period(period, request.user)
    except PayrollError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Payroll period {period.label} closed.")
    return redirect("payroll-period", pk=pk)


@role_required(*PRIVILEGED)
@require_POST
def record_status(request, pk):
    record = get_object_or_404(PayrollRecord.objects.select_related("employee", "period"), pk=pk)
    try:
        set_payment_status(record, request.POST.get("status", ""), request.user)
    except PayrollError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{record.employee.employee_code} marked {record.get_payment_status_display().lower()}.")
    return redirect("payroll-period", pk=record.period_id)


@role_required(*PRIVILEGED)
@require_POST
def record_payslip(request, pk):
    record = get_object_or_404(PayrollRecord.objects.select_related("employee__user", "period"), pk=pk)
    try:
        generate_payslip(record, request.user)
    except PayrollError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Payslip for {record.employee.employee_code} generated.")
    return redirect("payroll-period", pk=record.period_id)


@login_required
def my_payslips(request):
    """Every logged-in user sees only their own payroll records here."""
    records = PayrollRecord.objects.select_related("period").filter(employee__user=request.user)
    return render(request, "payroll/my_payslips.html", {"records": records})


@login_required
def payslip_download(request, pk):
    """
    Download one payslip PDF.

    Allowed for Admin/HR and for the employee the payslip belongs to. Anyone else
    gets a 404, so the existence of other people's payslips is not revealed.
    Payslip files are never served from a public media URL.
    """
    record = get_object_or_404(PayrollRecord.objects.select_related("employee", "period"), pk=pk)
    if request.user.role not in PRIVILEGED and record.employee.user_id != request.user.id:
        raise Http404
    if not record.payslip_file:
        raise Http404("No payslip has been generated yet.")
    try:
        handle = record.payslip_file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("The payslip file is missing.") from exc
    logger.info("payslip %s downloaded by %s", record.pk, request.user)
    return FileResponse(
        handle,
        as_attachment=True,
        filename=f"payslip-{record.period.label}-{record.employee.employee_code}.pdf",
        content_type="application/pdf",
    )


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
class PayrollRecordListView(ListAPIView):
    """
    Payroll records.

    Admin/HR see every record (optionally filtered by ?period=YYYY-MM). An employee
    sees only their own records. Anonymous users are rejected by IsAuthenticated.
    """

    serializer_class = PayrollRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PayrollRecord.objects.select_related("employee", "period")
        user = self.request.user
        if user.role not in PRIVILEGED:
            return queryset.filter(employee__user=user)
        label = self.request.query_params.get("period")
        if label:
            try:
                year, month = (int(part) for part in label.split("-"))
            except ValueError:
                return queryset.none()
            queryset = queryset.filter(period__year=year, period__month=month)
        return queryset


class PayrollRecordStatusView(APIView):
    """Admin/HR move a record between pending, on hold and paid."""

    permission_classes = [IsHROrAdmin]

    def post(self, request, pk):
        record = get_object_or_404(PayrollRecord.objects.select_related("employee", "period"), pk=pk)
        serializer = PayrollStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            set_payment_status(record, serializer.validated_data["status"], request.user)
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=http.HTTP_409_CONFLICT)
        return Response(PayrollRecordSerializer(record).data)


class PayrollPeriodListCreateView(ListCreateAPIView):
    permission_classes = [IsHROrAdmin]
    serializer_class = PayrollPeriodSerializer
    queryset = PayrollPeriod.objects.all()


class _PeriodActionView(APIView):
    permission_classes = [IsHROrAdmin]

    def run(self, period, user):
        raise NotImplementedError

    def post(self, request, pk):
        period = get_object_or_404(PayrollPeriod, pk=pk)
        try:
            result = self.run(period, request.user)
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=http.HTTP_409_CONFLICT)
        return Response(result)


class PeriodGenerateView(_PeriodActionView):
    def run(self, period, user):
        summary = generate_payroll(period, user)
        summary["errors"] = [{"employee": code, "reason": reason} for code, reason in summary["errors"]]
        return summary


class PeriodPayslipsView(_PeriodActionView):
    def run(self, period, user):
        return {"payslips_generated": generate_payslips_for_period(period, user)}


class PeriodCloseView(_PeriodActionView):
    def run(self, period, user):
        return PayrollPeriodSerializer(close_period(period, user)).data


class SalaryComponentListCreateView(ListCreateAPIView):
    permission_classes = [IsHROrAdmin]
    serializer_class = SalaryComponentSerializer
    queryset = SalaryComponent.objects.all()

    def perform_create(self, serializer):
        component = serializer.save()
        record_event(self.request.user, AuditEvent.Action.CREATE, "SalaryComponent", component.pk, {"name": component.name})


class SalaryComponentDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsHROrAdmin]
    serializer_class = SalaryComponentSerializer
    queryset = SalaryComponent.objects.all()

    def perform_update(self, serializer):
        component = serializer.save()
        record_event(self.request.user, AuditEvent.Action.UPDATE, "SalaryComponent", component.pk, {"name": component.name})


class EmployeeSalaryListCreateView(ListCreateAPIView):
    """Salary components of employees. Admin/HR only: employees never see these rows."""

    permission_classes = [IsHROrAdmin]
    serializer_class = EmployeeSalaryComponentSerializer

    def get_queryset(self):
        queryset = EmployeeSalaryComponent.objects.select_related("employee", "component")
        employee = self.request.query_params.get("employee")
        return queryset.filter(employee_id=employee) if employee else queryset

    def perform_create(self, serializer):
        instance = serializer.save()
        audit_salary_change(self.request.user, AuditEvent.Action.CREATE, instance)


class EmployeeSalaryDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsHROrAdmin]
    serializer_class = EmployeeSalaryComponentSerializer
    queryset = EmployeeSalaryComponent.objects.select_related("employee", "component")

    def perform_update(self, serializer):
        before = serializer.instance.value
        instance = serializer.save()
        audit_salary_change(self.request.user, AuditEvent.Action.UPDATE, instance, before)

    def perform_destroy(self, instance):
        audit_salary_change(self.request.user, AuditEvent.Action.DELETE, instance, instance.value)
        instance.delete()
