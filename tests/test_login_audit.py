from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.reports.models import AuditEvent
from tests.helpers import PASSWORD, make_user


class LoginAuditTests(TestCase):
    def setUp(self):
        make_user("audit_user", User.Role.EMPLOYEE)

    def test_failed_login_is_audited_without_password(self):
        self.client.post(
            reverse("login"), {"username": "audit_user", "password": "not-the-password"}
        )
        event = AuditEvent.objects.get(action=AuditEvent.Action.LOGIN)
        self.assertIsNone(event.actor)
        self.assertEqual(event.changes, {"result": "failed", "username": "audit_user"})
        self.assertNotIn("not-the-password", str(event.changes))

    def test_failed_login_for_unknown_user_is_audited(self):
        self.client.post(reverse("login"), {"username": "nobody", "password": "x"})
        event = AuditEvent.objects.get(action=AuditEvent.Action.LOGIN)
        self.assertEqual(event.changes["username"], "nobody")

    def test_successful_login_is_not_marked_failed(self):
        self.client.post(reverse("login"), {"username": "audit_user", "password": PASSWORD})
        event = AuditEvent.objects.get(action=AuditEvent.Action.LOGIN)
        self.assertEqual(event.actor.username, "audit_user")
        self.assertEqual(event.changes, {})
