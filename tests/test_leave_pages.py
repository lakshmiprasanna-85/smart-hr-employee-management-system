from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.leave_management.models import LeaveRequest

from .helpers import PASSWORD, make_employee, make_leave_type, make_user

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE
APPLY = {"start_date": "2026-11-02", "end_date": "2026-11-04", "reason": "Family function"}


class LeavePagesTestCase(TestCase):
    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice_user = make_user("alice", EMPLOYEE)
        self.alice = make_employee(self.alice_user, "EMP001")
        self.bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        self.leave_type = make_leave_type()

    def login(self, username):
        self.client.logout()
        self.client.login(username=username, password=PASSWORD)

    def apply(self, username="alice", **extra):
        self.login(username)
        return self.client.post(reverse("leave-home"), {**APPLY, "leave_type": self.leave_type.pk, **extra}, follow=True)

    def make_request(self, employee, reason="Trip"):
        return LeaveRequest.objects.create(
            employee=employee, leave_type=self.leave_type, start_date="2026-11-02", end_date="2026-11-03", reason=reason
        )


class ApplyAndCancelTests(LeavePagesTestCase):
    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("leave-home"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_employee_applies_through_the_form(self):
        response = self.apply()
        self.assertContains(response, "Leave request submitted.")
        leave = LeaveRequest.objects.get()
        self.assertEqual((leave.employee, leave.status, leave.total_days), (self.alice, "pending", 3))

    def test_invalid_dates_show_the_same_message_as_the_api(self):
        response = self.apply(start_date="2026-11-05", end_date="2026-11-01")
        self.assertContains(response, "End date cannot be before start date.")
        self.assertEqual(LeaveRequest.objects.count(), 0)
        self.assertContains(response, "Family function")  # the form keeps what was typed

    def test_missing_fields_show_errors_not_a_crash(self):
        self.login("alice")
        response = self.client.post(reverse("leave-home"), {"reason": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    def test_inactive_leave_type_is_refused(self):
        self.leave_type.is_active = False
        self.leave_type.save()
        response = self.apply()
        self.assertEqual(LeaveRequest.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_account_without_profile_cannot_apply(self):
        make_user("noprofile", EMPLOYEE)
        response = self.apply("noprofile")
        self.assertContains(response, "no employee profile")
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_my_requests_lists_only_my_own(self):
        self.make_request(self.alice, reason="Alice trip")
        self.make_request(self.bob, reason="Bob secret reason")
        self.login("alice")
        response = self.client.get(reverse("leave-home"))
        self.assertEqual([r.employee_id for r in response.context["requests"]], [self.alice.pk])

    def test_cancel_own_request(self):
        leave = self.make_request(self.alice)
        self.login("alice")
        response = self.client.post(reverse("leave-cancel", kwargs={"pk": leave.pk}), follow=True)
        self.assertContains(response, "Leave request cancelled.")
        self.assertEqual(LeaveRequest.objects.get().status, "cancelled")

    def test_cannot_cancel_someone_elses_request(self):
        leave = self.make_request(self.bob)
        self.login("alice")
        self.client.post(reverse("leave-cancel", kwargs={"pk": leave.pk}))
        self.assertEqual(LeaveRequest.objects.get().status, "pending")

    def test_cancelling_twice_shows_the_state_machine_message(self):
        leave = self.make_request(self.alice)
        self.login("alice")
        url = reverse("leave-cancel", kwargs={"pk": leave.pk})
        self.client.post(url)
        response = self.client.post(url, follow=True)
        self.assertContains(response, "Cannot move a cancelled request to cancelled.")

    def test_cancel_is_post_only(self):
        leave = self.make_request(self.alice)
        self.login("alice")
        self.assertEqual(self.client.get(reverse("leave-cancel", kwargs={"pk": leave.pk})).status_code, 405)


class ReviewTests(LeavePagesTestCase):
    def decide(self, leave, decision, note="", username="hr_user"):
        self.login(username)
        return self.client.post(
            reverse("leave-decide", kwargs={"pk": leave.pk}), {"decision": decision, "note": note}, follow=True
        )

    def test_employee_cannot_open_review_or_decide(self):
        leave = self.make_request(self.bob)
        self.login("alice")
        self.assertEqual(self.client.get(reverse("leave-review")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("leave-decide", kwargs={"pk": leave.pk}), {"decision": "approved"}).status_code, 403
        )
        self.assertEqual(LeaveRequest.objects.get().status, "pending")

    def test_hr_sees_pending_requests(self):
        self.make_request(self.alice, reason="Alice trip")
        self.login("hr_user")
        response = self.client.get(reverse("leave-review"))
        self.assertContains(response, "EMP001")
        self.assertEqual(len(response.context["pending"]), 1)

    def test_hr_approves_with_a_note_and_the_employee_is_emailed(self):
        leave = self.make_request(self.alice)
        response = self.decide(leave, "approved", "Enjoy")
        self.assertContains(response, "approved")
        leave.refresh_from_db()
        self.assertEqual((leave.status, leave.reviewer_note, leave.reviewed_by), ("approved", "Enjoy", self.hr))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        self.assertIn("Enjoy", mail.outbox[0].body)
        self.assertTrue(leave.history.filter(from_status="pending", to_status="approved").exists())

    def test_hr_rejects(self):
        leave = self.make_request(self.alice)
        self.decide(leave, "rejected", "Team is short")
        self.assertEqual(LeaveRequest.objects.get().status, "rejected")
        self.assertIn("rejected", mail.outbox[0].subject)

    def test_deciding_twice_is_refused_with_a_message(self):
        leave = self.make_request(self.alice)
        self.decide(leave, "approved")
        response = self.decide(leave, "rejected")
        self.assertContains(response, "Cannot move a approved request to rejected.")
        self.assertEqual(LeaveRequest.objects.get().status, "approved")

    def test_nobody_decides_their_own_request(self):
        make_employee(self.hr, "EMPHR")
        leave = self.make_request(self.hr.employee_profile)
        response = self.decide(leave, "approved")
        self.assertContains(response, "You cannot approve or reject your own leave request.")
        self.assertEqual(LeaveRequest.objects.get().status, "pending")

    def test_own_request_shows_no_approve_button(self):
        make_employee(self.hr, "EMPHR")
        self.make_request(self.hr.employee_profile)
        self.login("hr_user")
        self.assertContains(self.client.get(reverse("leave-review")), "someone else must decide it")

    def test_unknown_decision_value_is_refused(self):
        leave = self.make_request(self.alice)
        response = self.decide(leave, "cancelled")
        self.assertContains(response, "Choose approve or reject.")
        self.assertEqual(LeaveRequest.objects.get().status, "pending")

    def test_decide_is_post_only(self):
        leave = self.make_request(self.alice)
        self.login("hr_user")
        self.assertEqual(self.client.get(reverse("leave-decide", kwargs={"pk": leave.pk})).status_code, 405)

    def test_recent_decisions_are_listed(self):
        leave = self.make_request(self.alice)
        self.decide(leave, "approved")
        response = self.client.get(reverse("leave-review"))
        self.assertEqual(len(response.context["recent"]), 1)
        self.assertEqual(len(response.context["pending"]), 0)
