from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .helpers import PASSWORD, make_employee, make_payroll, make_period, make_user

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE


class PayrollAccessTests(TestCase):
    """Payroll data must only be visible to authorised roles."""

    def setUp(self):
        self.admin = make_user("admin_user", ADMIN)
        self.hr = make_user("hr_user", HR)
        self.alice_user = make_user("alice", EMPLOYEE)
        self.bob_user = make_user("bob", EMPLOYEE)
        self.alice = make_employee(self.alice_user, "EMP001")
        self.bob = make_employee(self.bob_user, "EMP002")
        period = make_period()
        make_payroll(self.alice, period)
        make_payroll(self.bob, period, gross="60000.00", deductions="6000.00")

    def _codes(self, username):
        self.client.login(username=username, password=PASSWORD)
        response = self.client.get(reverse("api-payroll-records"))
        self.assertEqual(response.status_code, 200)
        return sorted(row["employee_code"] for row in response.json())

    # --- management page -------------------------------------------------
    def test_payroll_page_anonymous_redirects_to_login(self):
        response = self.client.get(reverse("payroll-home"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_payroll_page_forbidden_for_employee(self):
        self.client.login(username="alice", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("payroll-home")).status_code, 403)

    def test_payroll_page_allowed_for_hr_and_admin(self):
        for username in ("hr_user", "admin_user"):
            with self.subTest(user=username):
                self.client.login(username=username, password=PASSWORD)
                self.assertEqual(self.client.get(reverse("payroll-home")).status_code, 200)
                self.client.logout()

    # --- API ---------------------------------------------------------------
    def test_api_rejects_anonymous(self):
        self.assertEqual(self.client.get(reverse("api-payroll-records")).status_code, 403)

    def test_employee_sees_only_own_records(self):
        self.assertEqual(self._codes("alice"), ["EMP001"])

    def test_employee_cannot_see_colleague_records(self):
        self.assertNotIn("EMP002", self._codes("alice"))

    def test_user_without_employee_profile_sees_nothing(self):
        make_user("noprofile", EMPLOYEE)
        self.assertEqual(self._codes("noprofile"), [])

    def test_hr_and_admin_see_all_records(self):
        self.assertEqual(self._codes("hr_user"), ["EMP001", "EMP002"])
        self.client.logout()
        self.assertEqual(self._codes("admin_user"), ["EMP001", "EMP002"])
