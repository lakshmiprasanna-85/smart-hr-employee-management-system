from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.employees.models import Department, Employee
from apps.leave_management.models import LeaveRequest
from apps.leave_management.states import LeaveStatus

from .helpers import PASSWORD, make_employee, make_leave_type, make_payroll, make_period, make_user

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE


def shift_month(year, month, step):
    month += step
    if month < 1:
        return year - 1, 12
    if month > 12:
        return year + 1, 1
    return year, month


class ReportPageAccessTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin_user", ADMIN)
        self.hr = make_user("hr_user", HR)
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("reports-home"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_employee_gets_403(self):
        self.client.login(username="alice", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("reports-home")).status_code, 403)

    def test_admin_and_hr_can_open_the_page(self):
        for username in ("admin_user", "hr_user"):
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password=PASSWORD)
                self.assertEqual(self.client.get(reverse("reports-home")).status_code, 200)

    def test_navigation_and_dashboards_link_to_reports(self):
        self.client.login(username="hr_user", password=PASSWORD)
        self.assertContains(self.client.get(reverse("dashboard-hr")), reverse("reports-home"))
        self.client.logout()
        self.client.login(username="admin_user", password=PASSWORD)
        self.assertContains(self.client.get(reverse("dashboard-admin")), reverse("reports-home"))

    def test_invalid_month_and_year_fall_back_to_today(self):
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.get(reverse("reports-home") + "?month=99&year=abc")
        today = timezone.localdate()
        self.assertEqual(response.context["month"], today.month)
        self.assertEqual(response.context["year"], today.year)


class ReportPageDataTests(TestCase):
    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.engineering = Department.objects.create(name="Engineering")
        self.finance = Department.objects.create(name="Finance")
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")
        self.alice.department = self.engineering
        self.alice.save()
        self.bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        self.bob.department = self.engineering
        self.bob.save()
        self.carol = make_employee(make_user("carol", EMPLOYEE), "EMP003")
        self.carol.department = self.finance
        self.carol.save()
        self.former = make_employee(make_user("former", EMPLOYEE), "EMP004")
        self.former.department = self.finance
        self.former.employment_status = Employee.Status.TERMINATED
        self.former.save()

        self.today = timezone.localdate()
        Attendance.objects.create(
            employee=self.alice, date=self.today, check_in=timezone.now(), status="present"
        )
        Attendance.objects.create(employee=self.bob, date=self.today, status="late")
        Attendance.objects.create(employee=self.carol, date=self.today, status="absent")

        leave_type = make_leave_type()
        LeaveRequest.objects.create(
            employee=self.alice,
            leave_type=leave_type,
            start_date=self.today,
            end_date=self.today + timedelta(days=1),
            status=LeaveStatus.PENDING,
        )
        LeaveRequest.objects.create(
            employee=self.bob,
            leave_type=leave_type,
            start_date=self.today,
            end_date=self.today,
            status=LeaveStatus.APPROVED,
        )

        self.current_period = make_period(self.today.year, self.today.month)
        make_payroll(self.alice, self.current_period, gross="50000.00", deductions="5000.00")
        make_payroll(self.bob, self.current_period, gross="40000.00", deductions="4000.00")
        prev_year, prev_month = shift_month(self.today.year, self.today.month, -1)
        self.previous_period = make_period(prev_year, prev_month)
        make_payroll(self.carol, self.previous_period, gross="30000.00", deductions="3000.00")

        self.client.login(username="hr_user", password=PASSWORD)

    def test_kpis_are_defined_once_and_exclude_terminated_employees(self):
        response = self.client.get(reverse("reports-home"))
        self.assertEqual(response.context["headcount"], 3)
        self.assertEqual(response.context["present_today"], 1)
        self.assertEqual(response.context["pending_leave"], 1)
        self.assertEqual(response.context["latest_period"], self.current_period)
        self.assertEqual(response.context["latest_net"], Decimal("81000.00"))

    def test_headcount_chart_groups_employees_by_department(self):
        response = self.client.get(reverse("reports-home"))
        rows = {row["label"]: row["count"] for row in response.context["by_department"]["rows"]}
        self.assertEqual(rows, {"Engineering": 2, "Finance": 1})
        self.assertEqual(response.context["by_department"]["total"], 3)

    def test_attendance_chart_counts_every_status(self):
        response = self.client.get(reverse("reports-home"))
        counts = {
            row["status"]: row["count"] for row in response.context["attendance"]["rows"]
        }
        self.assertEqual(counts["present"], 1)
        self.assertEqual(counts["late"], 1)
        self.assertEqual(counts["absent"], 1)
        self.assertEqual(response.context["attendance"]["total"], 3)

    def test_leave_chart_uses_requests_starting_in_the_month(self):
        response = self.client.get(reverse("reports-home"))
        counts = {row["status"]: row["count"] for row in response.context["leave"]["rows"]}
        self.assertEqual(counts["pending"], 1)
        self.assertEqual(counts["approved"], 1)
        self.assertEqual(response.context["leave"]["total"], 2)

    def test_payroll_chart_lists_periods_oldest_first(self):
        response = self.client.get(reverse("reports-home"))
        labels = [row["label"] for row in response.context["payroll"]["rows"]]
        self.assertEqual(
            labels, [self.previous_period.label, self.current_period.label]
        )
        self.assertEqual(response.context["payroll"]["latest_total"], Decimal("81000.00"))

    def test_a_month_without_data_shows_an_empty_state(self):
        response = self.client.get(reverse("reports-home") + "?year=2020&month=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["attendance"]["total"], 0)
        self.assertContains(response, "No attendance recorded for January 2020.")

    def test_the_page_renders_bars_without_external_scripts(self):
        response = self.client.get(reverse("reports-home"))
        self.assertContains(response, "Headcount by department")
        self.assertContains(response, "Payroll net total by period")
        self.assertContains(response, "Download reports")
        self.assertNotContains(response, "<script")
