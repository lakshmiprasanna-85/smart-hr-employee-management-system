from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .helpers import PASSWORD, make_user

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE

DASHBOARDS = {
    "dashboard-admin": {ADMIN: 200, HR: 403, EMPLOYEE: 403},
    "dashboard-hr": {ADMIN: 200, HR: 200, EMPLOYEE: 403},
    "dashboard-employee": {ADMIN: 200, HR: 200, EMPLOYEE: 200},
}


class AuthenticationTests(TestCase):
    def setUp(self):
        self.users = {role: make_user(f"{role}_user", role) for role in (ADMIN, HR, EMPLOYEE)}

    def test_login_page_loads(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse("login"), {"username": "admin_user", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_each_role_lands_on_its_own_dashboard(self):
        expected = {
            ADMIN: "dashboard-admin",
            HR: "dashboard-hr",
            EMPLOYEE: "dashboard-employee",
        }
        for role, url_name in expected.items():
            with self.subTest(role=role):
                self.client.logout()
                self.client.post(
                    reverse("login"), {"username": f"{role}_user", "password": PASSWORD}
                )
                response = self.client.get(reverse("dashboard"))
                self.assertRedirects(
                    response, reverse(url_name), fetch_redirect_response=False
                )

    def test_logout_ends_session(self):
        self.client.login(username="employee_user", password=PASSWORD)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_createsuperuser_gets_admin_role(self):
        superuser = User.objects.create_superuser("root", "root@example.com", PASSWORD)
        self.assertEqual(superuser.role, ADMIN)

    def test_default_role_is_employee(self):
        self.assertEqual(User.objects.create_user("plain", password=PASSWORD).role, EMPLOYEE)


class DashboardPermissionTests(TestCase):
    """Role-permission matrix: every dashboard x every role, plus anonymous."""

    def setUp(self):
        for role in (ADMIN, HR, EMPLOYEE):
            make_user(f"{role}_user", role)

    def test_anonymous_is_redirected_to_login(self):
        for url_name in DASHBOARDS:
            with self.subTest(url=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_dashboard_access_matches_role_matrix(self):
        for url_name, per_role in DASHBOARDS.items():
            for role, expected_status in per_role.items():
                with self.subTest(url=url_name, role=role):
                    self.client.login(username=f"{role}_user", password=PASSWORD)
                    response = self.client.get(reverse(url_name))
                    self.assertEqual(response.status_code, expected_status)
                    self.client.logout()

    def test_api_me_requires_login_and_returns_role(self):
        self.assertEqual(self.client.get(reverse("api-me")).status_code, 403)
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.get(reverse("api-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], HR)
