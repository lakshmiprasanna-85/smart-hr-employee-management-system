from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.reports.models import NotificationLog
from apps.reports.notifications import send_notification

from .helpers import PASSWORD, make_employee, make_leave_type, make_user

HR, EMPLOYEE = User.Role.HR, User.Role.EMPLOYEE


class SendNotificationTests(TestCase):
    def setUp(self):
        self.user = make_user("alice")

    def _send(self, user=None):
        return send_notification(
            "payslip_available", user or self.user, "Your payslip is ready",
            "emails/payslip_available.txt", {"period": "2026-09"},
        )

    def test_success_sends_email_and_logs_sent(self):
        log = self._send()
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertIsNotNone(log.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        self.assertIn("2026-09", mail.outbox[0].body)

    def test_mail_failure_is_logged_and_not_raised(self):
        with mock.patch("apps.reports.notifications.send_mail", side_effect=OSError("SMTP down")):
            log = self._send()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("SMTP down", log.error_message)
        self.assertEqual(len(mail.outbox), 0)

    def test_user_without_email_is_logged_as_failed(self):
        self.user.email = ""
        self.user.save()
        log = self._send()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("no email", log.error_message)
        self.assertEqual(len(mail.outbox), 0)

    def test_every_attempt_creates_one_log_row(self):
        self._send()
        with mock.patch("apps.reports.notifications.send_mail", side_effect=OSError("x")):
            self._send()
        self.assertEqual(NotificationLog.objects.count(), 2)

    def test_payslip_email_has_no_salary_figures(self):
        self._send()
        self.assertNotRegex(mail.outbox[0].body, r"\d{2,3},?\d{3}")


class LeaveDecisionEmailTests(TestCase):
    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice_user = make_user("alice", EMPLOYEE)
        self.alice = make_employee(self.alice_user, "EMP001")
        self.leave_type = make_leave_type()
        self.client.login(username="alice", password=PASSWORD)
        self.request_id = self.client.post(
            reverse("api-leave-requests"),
            {"leave_type": self.leave_type.pk, "start_date": "2026-11-02", "end_date": "2026-11-04"},
            content_type="application/json",
        ).json()["id"]
        self.client.logout()
        self.client.login(username="hr_user", password=PASSWORD)

    def _decide(self, decision, note=""):
        return self.client.post(
            reverse("api-leave-decide", kwargs={"pk": self.request_id}),
            {"decision": decision, "note": note},
            content_type="application/json",
        )

    def test_approval_emails_the_employee(self):
        self.assertEqual(self._decide("approved", "Enjoy").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["alice@example.com"])
        self.assertIn("approved", message.subject)
        self.assertIn("Enjoy", message.body)
        self.assertIn("3 days", message.body)

    def test_rejection_emails_the_employee(self):
        self._decide("rejected", "Team is short")
        self.assertIn("rejected", mail.outbox[0].subject)

    def test_cancellation_sends_no_email(self):
        self._decide("cancelled")
        self.assertEqual(len(mail.outbox), 0)

    def test_failed_decision_sends_no_email(self):
        self._decide("approved")
        mail.outbox.clear()
        self.assertEqual(self._decide("approved").status_code, 409)
        self.assertEqual(len(mail.outbox), 0)

    def test_mail_outage_does_not_undo_the_decision(self):
        with mock.patch("apps.reports.notifications.send_mail", side_effect=OSError("SMTP down")):
            response = self._decide("approved")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "approved")
        self.assertEqual(NotificationLog.objects.get().status, NotificationLog.Status.FAILED)
