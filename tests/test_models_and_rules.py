from datetime import date, datetime, timezone

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.attendance.models import Attendance
from apps.employees.models import Employee
from apps.leave_management.models import LeaveRequest, LeaveType
from apps.leave_management.states import ALLOWED_TRANSITIONS, LeaveStatus, can_transition
from apps.payroll.models import PayrollPeriod
from apps.reports.models import AuditEvent

from .helpers import PASSWORD, make_employee, make_payroll, make_period, make_user


class EmployeeRuleTests(TestCase):
    def setUp(self):
        self.employee = make_employee(make_user("alice"), "EMP001")

    def test_employee_code_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_employee(make_user("bob"), "EMP001")

    def test_one_employee_record_per_user(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Employee.objects.create(
                    user=self.employee.user, employee_code="EMP999", joining_date=date(2025, 2, 1)
                )

    def test_exit_date_cannot_precede_joining_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Employee.objects.create(
                    user=make_user("carol"),
                    employee_code="EMP003",
                    joining_date=date(2025, 5, 1),
                    exit_date=date(2025, 4, 1),
                )


class AttendanceRuleTests(TestCase):
    def setUp(self):
        self.employee = make_employee(make_user("alice"), "EMP001")

    def test_one_record_per_employee_per_day(self):
        Attendance.objects.create(employee=self.employee, date=date(2026, 9, 1))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(employee=self.employee, date=date(2026, 9, 1))

    def test_checkout_must_be_after_checkin(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    employee=self.employee,
                    date=date(2026, 9, 2),
                    check_in=datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
                    check_out=datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc),
                )

    def test_valid_checkin_checkout_is_saved(self):
        record = Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 9, 3),
            check_in=datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
            check_out=datetime(2026, 9, 3, 17, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(record.status, Attendance.Status.PRESENT)


class LeaveRuleTests(TestCase):
    def setUp(self):
        self.employee = make_employee(make_user("alice"), "EMP001")
        self.leave_type = LeaveType.objects.create(name="Casual", annual_quota_days=12)

    def test_new_request_defaults_to_pending(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 9, 10),
            end_date=date(2026, 9, 12),
        )
        self.assertEqual(leave.status, LeaveStatus.PENDING)
        self.assertEqual(leave.total_days, 3)

    def test_end_date_cannot_precede_start_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LeaveRequest.objects.create(
                    employee=self.employee,
                    leave_type=self.leave_type,
                    start_date=date(2026, 9, 12),
                    end_date=date(2026, 9, 10),
                )

    def test_allowed_transitions(self):
        self.assertTrue(can_transition(LeaveStatus.PENDING, LeaveStatus.APPROVED))
        self.assertTrue(can_transition(LeaveStatus.PENDING, LeaveStatus.REJECTED))
        self.assertTrue(can_transition(LeaveStatus.PENDING, LeaveStatus.CANCELLED))
        self.assertTrue(can_transition(LeaveStatus.APPROVED, LeaveStatus.CANCELLED))

    def test_invalid_transitions_are_blocked(self):
        self.assertFalse(can_transition(LeaveStatus.APPROVED, LeaveStatus.REJECTED))
        self.assertFalse(can_transition(LeaveStatus.APPROVED, LeaveStatus.PENDING))
        self.assertFalse(can_transition(LeaveStatus.REJECTED, LeaveStatus.APPROVED))
        self.assertFalse(can_transition(LeaveStatus.CANCELLED, LeaveStatus.PENDING))

    def test_final_states_have_no_exits(self):
        self.assertEqual(ALLOWED_TRANSITIONS[LeaveStatus.REJECTED], set())
        self.assertEqual(ALLOWED_TRANSITIONS[LeaveStatus.CANCELLED], set())


class PayrollRuleTests(TestCase):
    def setUp(self):
        self.employee = make_employee(make_user("alice"), "EMP001")
        self.period = make_period()

    def test_one_period_per_month(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_period(2026, 9)

    def test_one_payroll_record_per_employee_per_period(self):
        make_payroll(self.employee, self.period)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_payroll(self.employee, self.period)

    def test_negative_amounts_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_payroll(self.employee, make_period(2026, 8), gross="-1.00")

    def test_period_label(self):
        self.assertEqual(PayrollPeriod.objects.get(pk=self.period.pk).label, "2026-09")


class AuditTests(TestCase):
    def test_login_creates_audit_event(self):
        user = make_user("alice")
        self.client.post(reverse("login"), {"username": "alice", "password": PASSWORD})
        event = AuditEvent.objects.get(action=AuditEvent.Action.LOGIN)
        self.assertEqual(event.actor, user)
        self.assertEqual(event.entity_id, str(user.pk))
