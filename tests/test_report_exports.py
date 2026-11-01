import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.employees.models import Department
from apps.leave_management.models import LeaveRequest
from apps.leave_management.states import LeaveStatus
from apps.reports.models import AuditEvent

from .helpers import PASSWORD, make_employee, make_leave_type, make_payroll, make_period, make_user
from .test_reports_pages import shift_month

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE
KINDS = ("employees", "attendance", "leave", "payroll")
FORMATS = ("csv", "xlsx", "pdf")


def export_url(kind, fmt, query=""):
    url = reverse("report-export", kwargs={"kind": kind, "fmt": fmt})
    return f"{url}?{query}" if query else url


def csv_rows(response):
    body = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(body)))


class ExportAccessTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin_user", ADMIN)
        self.hr = make_user("hr_user", HR)
        self.employee = make_employee(make_user("alice", EMPLOYEE), "EMP001")

    def test_anonymous_is_redirected_for_every_report_and_format(self):
        for kind in KINDS:
            for fmt in FORMATS:
                with self.subTest(kind=kind, fmt=fmt):
                    response = self.client.get(export_url(kind, fmt))
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(reverse("login")))

    def test_employee_cannot_download_any_report(self):
        self.client.login(username="alice", password=PASSWORD)
        for kind in KINDS:
            for fmt in FORMATS:
                with self.subTest(kind=kind, fmt=fmt):
                    self.assertEqual(self.client.get(export_url(kind, fmt)).status_code, 403)

    def test_admin_and_hr_can_download_every_report_and_format(self):
        for username in ("admin_user", "hr_user"):
            self.client.login(username=username, password=PASSWORD)
            for kind in KINDS:
                for fmt in FORMATS:
                    with self.subTest(kind=kind, fmt=fmt):
                        response = self.client.get(export_url(kind, fmt))
                        self.assertEqual(response.status_code, 200)

    def test_unknown_report_or_format_is_not_found(self):
        self.client.login(username="hr_user", password=PASSWORD)
        self.assertEqual(self.client.get(export_url("salaries", "csv")).status_code, 404)
        self.assertEqual(self.client.get(export_url("employees", "docx")).status_code, 404)

    def test_exports_are_get_only(self):
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.post(export_url("employees", "csv"))
        self.assertEqual(response.status_code, 405)


class ExportContentTests(TestCase):
    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.engineering = Department.objects.create(name="Engineering")
        self.risky = Department.objects.create(name='=HYPERLINK("http://example.org","x")')
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")
        self.alice.department = self.engineering
        self.alice.phone = "9999999999"
        self.alice.address = "1 Secret Street"
        self.alice.save()
        self.bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        self.bob.department = self.risky
        self.bob.save()

        self.today = timezone.localdate()
        Attendance.objects.create(
            employee=self.alice, date=self.today, check_in=timezone.now(), status="present"
        )
        last_year, last_month = shift_month(self.today.year, self.today.month, -1)
        Attendance.objects.create(
            employee=self.bob,
            date=self.today.replace(year=last_year, month=last_month, day=1),
            status="absent",
        )

        leave_type = make_leave_type()
        LeaveRequest.objects.create(
            employee=self.alice,
            leave_type=leave_type,
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
            status=LeaveStatus.PENDING,
        )

        self.period = make_period(self.today.year, self.today.month)
        make_payroll(self.alice, self.period, gross="50000.00", deductions="5000.00")
        make_payroll(self.bob, self.period, gross="40000.00", deductions="4000.00")

        self.client.login(username="hr_user", password=PASSWORD)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------
    def test_csv_employee_report_has_headers_and_no_personal_details(self):
        response = self.client.get(export_url("employees", "csv"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(".csv", response["Content-Disposition"])
        rows = csv_rows(response)
        self.assertEqual(
            rows[0],
            ["Employee no.", "Name", "Department", "Job title", "Status", "Joined"],
        )
        body = response.content.decode("utf-8")
        self.assertIn("EMP001", body)
        self.assertNotIn("9999999999", body)
        self.assertNotIn("1 Secret Street", body)

    def test_csv_formula_injection_is_neutralised(self):
        response = self.client.get(export_url("employees", "csv"))
        rows = csv_rows(response)
        department_cells = [row[2] for row in rows[1:]]
        self.assertIn('\'=HYPERLINK("http://example.org","x")', department_cells)

    def test_csv_attendance_is_limited_to_the_selected_month(self):
        response = self.client.get(
            export_url("attendance", "csv", f"year={self.today.year}&month={self.today.month}")
        )
        rows = csv_rows(response)
        self.assertEqual(len(rows), 2)  # header + the current-month record
        self.assertEqual(rows[1][0], "EMP001")
        self.assertNotEqual(rows[1][3], "-")

    def test_csv_leave_report_includes_days(self):
        response = self.client.get(
            export_url("leave", "csv", f"year={self.today.year}&month={self.today.month}")
        )
        rows = csv_rows(response)
        self.assertEqual(rows[0][5], "Days")
        self.assertEqual(rows[1][5], "3")

    def test_csv_payroll_report_uses_the_requested_period(self):
        response = self.client.get(
            export_url("payroll", "csv", f"year={self.today.year}&month={self.today.month}")
        )
        rows = csv_rows(response)
        self.assertEqual(rows[0][0], "Period")
        self.assertEqual(rows[1][0], self.period.label)
        self.assertEqual(rows[1][5], "45000.00")

    def test_payroll_falls_back_to_the_latest_period(self):
        response = self.client.get(export_url("payroll", "csv", "year=2020&month=1"))
        rows = csv_rows(response)
        self.assertEqual(rows[1][0], self.period.label)

    def test_export_response_is_not_cached(self):
        response = self.client.get(export_url("payroll", "csv"))
        self.assertIn("no-store", response["Cache-Control"])

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    def test_xlsx_report_is_a_valid_workbook_with_numeric_pay(self):
        response = self.client.get(export_url("payroll", "xlsx"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        workbook = load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        self.assertEqual(sheet.cell(row=1, column=1).value, "Period")
        self.assertEqual(sheet.cell(row=2, column=1).value, self.period.label)
        self.assertEqual(sheet.cell(row=2, column=6).value, 45000.0)
        self.assertAlmostEqual(
            sum(sheet.cell(row=row, column=6).value for row in (2, 3)), 81000.0
        )

    def test_xlsx_formula_injection_is_neutralised(self):
        response = self.client.get(export_url("employees", "xlsx"))
        workbook = load_workbook(io.BytesIO(response.content))
        values = [cell.value for row in workbook.active.iter_rows() for cell in row]
        self.assertTrue(any(str(value).startswith("'=") for value in values if value))
        self.assertNotIn("9999999999", " ".join(str(value) for value in values))

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def test_pdf_report_is_a_pdf_download(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                response = self.client.get(export_url(kind, "pdf"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertIn(".pdf", response["Content-Disposition"])
                self.assertTrue(response.content.startswith(b"%PDF"))
                self.assertGreater(len(response.content), 1000)

    def test_pdf_builds_with_markup_in_the_data(self):
        self.alice.user.first_name = "<b>Alice</b> & Co"
        self.alice.user.save()
        response = self.client.get(export_url("employees", "pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------
    def test_every_export_is_audited(self):
        before = AuditEvent.objects.filter(action=AuditEvent.Action.EXPORT).count()
        self.client.get(export_url("attendance", "csv", "year=2026&month=2"))
        event = AuditEvent.objects.filter(action=AuditEvent.Action.EXPORT).latest("created_at")
        self.assertEqual(event.actor, self.hr)
        self.assertEqual(event.entity_type, "Report")
        self.assertEqual(event.entity_id, "attendance")
        self.assertEqual(event.changes["format"], "csv")
        self.assertEqual(event.changes["filters"], {"year": 2026, "month": 2})
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.EXPORT).count(), before + 1
        )
