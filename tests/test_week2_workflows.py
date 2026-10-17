"""Week 2 workflows: employee directory, attendance and leave approval."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.leave_management.models import LeaveRequest, LeaveStatusHistory

from .helpers import PASSWORD, make_employee, make_leave_type, make_user

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE


class EmployeeDirectoryTests(TestCase):
    """Personal fields stay hidden from non-privileged readers."""

    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice_user = make_user("alice", EMPLOYEE)
        self.alice = make_employee(self.alice_user, "EMP001")
        self.alice.phone = "9999900000"
        self.alice.save()

    def test_employee_list_hides_personal_fields_from_employee(self):
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get(reverse("api-employees"))
        self.assertEqual(response.status_code, 200)
        row = response.json()[0]
        self.assertNotIn("phone", row)
        self.assertNotIn("address", row)

    def test_hr_sees_personal_fields(self):
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.get(reverse("api-employees"))
        self.assertIn("phone", response.json()[0])

    def test_employee_cannot_create_employee(self):
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.post(
            reverse("api-employees"),
            {"employee_code": "EMP999", "joining_date": "2026-01-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_open_colleague_record(self):
        other = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get(
            reverse("api-employee-detail", kwargs={"pk": other.pk})
        )
        self.assertEqual(response.status_code, 403)


class AttendanceWorkflowTests(TestCase):
    """Check-in / check-out rules and the monthly summary."""

    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice_user = make_user("alice", EMPLOYEE)
        self.alice = make_employee(self.alice_user, "EMP001")

    def test_check_in_then_check_out(self):
        self.client.login(username="alice", password=PASSWORD)
        created = self.client.post(reverse("api-attendance-checkin"))
        self.assertEqual(created.status_code, 201)
        closed = self.client.post(reverse("api-attendance-checkout"))
        self.assertEqual(closed.status_code, 200)
        record = Attendance.objects.get(employee=self.alice)
        self.assertIsNotNone(record.check_in)
        self.assertIsNotNone(record.check_out)

    def test_duplicate_check_in_rejected(self):
        self.client.login(username="alice", password=PASSWORD)
        self.client.post(reverse("api-attendance-checkin"))
        again = self.client.post(reverse("api-attendance-checkin"))
        self.assertEqual(again.status_code, 409)

    def test_check_out_without_check_in_rejected(self):
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.post(reverse("api-attendance-checkout"))
        self.assertEqual(response.status_code, 409)

    def test_employee_sees_only_own_attendance(self):
        bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        Attendance.objects.create(employee=bob, date=date(2026, 10, 1))
        Attendance.objects.create(employee=self.alice, date=date(2026, 10, 1))
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get(reverse("api-attendance-records"))
        self.assertEqual(len(response.json()), 1)

    def test_summary_requires_hr_or_admin(self):
        self.client.login(username="alice", password=PASSWORD)
        self.assertEqual(
            self.client.get(reverse("api-attendance-summary")).status_code, 403
        )
        self.client.logout()
        self.client.login(username="hr_user", password=PASSWORD)
        self.assertEqual(
            self.client.get(reverse("api-attendance-summary")).status_code, 200
        )


class LeaveWorkflowTests(TestCase):
    """Apply, approve/reject with the state machine, and history."""

    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice_user = make_user("alice", EMPLOYEE)
        self.alice = make_employee(self.alice_user, "EMP001")
        self.leave_type = make_leave_type()

    def _apply(self):
        self.client.login(username="alice", password=PASSWORD)
        return self.client.post(
            reverse("api-leave-requests"),
            {
                "leave_type": self.leave_type.pk,
                "start_date": "2026-11-02",
                "end_date": "2026-11-04",
                "reason": "Family function",
            },
            content_type="application/json",
        )

    def test_employee_applies_and_sees_own_request(self):
        created = self._apply()
        self.assertEqual(created.status_code, 201)
        listing = self.client.get(reverse("api-leave-requests"))
        self.assertEqual(len(listing.json()), 1)
        self.assertEqual(listing.json()[0]["total_days"], 3)

    def test_end_before_start_rejected(self):
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.post(
            reverse("api-leave-requests"),
            {
                "leave_type": self.leave_type.pk,
                "start_date": "2026-11-04",
                "end_date": "2026-11-02",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_hr_approves_and_history_recorded(self):
        request_id = self._apply().json()["id"]
        self.client.logout()
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.post(
            reverse("api-leave-decide", kwargs={"pk": request_id}),
            {"decision": "approved", "note": "Ok"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        leave = LeaveRequest.objects.get(pk=request_id)
        self.assertEqual(leave.status, "approved")
        self.assertEqual(leave.reviewed_by, self.hr)
        self.assertTrue(
            LeaveStatusHistory.objects.filter(
                leave_request=leave, from_status="pending", to_status="approved"
            ).exists()
        )

    def test_approving_twice_is_a_conflict(self):
        request_id = self._apply().json()["id"]
        self.client.logout()
        self.client.login(username="hr_user", password=PASSWORD)
        url = reverse("api-leave-decide", kwargs={"pk": request_id})
        self.client.post(
            url, {"decision": "approved"}, content_type="application/json"
        )
        again = self.client.post(
            url, {"decision": "rejected"}, content_type="application/json"
        )
        self.assertEqual(again.status_code, 409)

    def test_employee_cannot_approve(self):
        request_id = self._apply().json()["id"]
        response = self.client.post(
            reverse("api-leave-decide", kwargs={"pk": request_id}),
            {"decision": "approved"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_can_cancel_own_pending_request(self):
        request_id = self._apply().json()["id"]
        response = self.client.post(
            reverse("api-leave-decide", kwargs={"pk": request_id}),
            {"decision": "cancelled"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, "cancelled")
