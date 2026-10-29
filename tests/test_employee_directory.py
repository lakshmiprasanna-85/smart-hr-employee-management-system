from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.employees.models import Department

from .helpers import PASSWORD, make_employee, make_user

HR, EMPLOYEE = User.Role.HR, User.Role.EMPLOYEE


class EmployeeDirectoryTests(TestCase):
    def setUp(self):
        make_user("hr_user", HR)
        eng = Department.objects.create(name="Engineering")
        fin = Department.objects.create(name="Finance")
        asha = make_user("asha", EMPLOYEE)
        asha.first_name, asha.last_name = "Asha", "Verma"
        asha.save()
        self.asha = make_employee(asha, "EMP001")
        self.asha.department, self.asha.phone = eng, "9999900000"
        self.asha.save()
        self.ravi = make_employee(make_user("ravi", EMPLOYEE), "EMP002", joining=date(2025, 2, 3))
        self.ravi.department, self.ravi.employment_status = fin, "probation"
        self.ravi.save()
        self.eng, self.fin = eng, fin

    def get(self, query="", username="hr_user"):
        self.client.login(username=username, password=PASSWORD)
        return self.client.get(reverse("employees-home") + query)

    def test_hr_sees_everyone_without_personal_details(self):
        response = self.get()
        self.assertContains(response, "EMP001")
        self.assertContains(response, "Asha Verma")
        self.assertContains(response, "EMP002")
        self.assertNotContains(response, "9999900000")  # phone numbers are not shown on this page

    def test_employee_cannot_open_the_directory(self):
        self.assertEqual(self.get(username="asha").status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        self.assertEqual(self.client.get(reverse("employees-home")).status_code, 302)

    def test_search_by_name_or_code(self):
        self.assertEqual([e.employee_code for e in self.get("?q=verma").context["employees"]], ["EMP001"])
        self.assertEqual([e.employee_code for e in self.get("?q=EMP002").context["employees"]], ["EMP002"])

    def test_filter_by_department_and_status(self):
        self.assertEqual([e.employee_code for e in self.get(f"?department={self.fin.pk}").context["employees"]], ["EMP002"])
        self.assertEqual([e.employee_code for e in self.get("?status=probation").context["employees"]], ["EMP002"])

    def test_junk_filters_are_ignored_not_errors(self):
        response = self.get("?department=abc&status=nonsense")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["employees"]), 2)

    def test_empty_result_shows_a_message(self):
        self.assertContains(self.get("?q=zzzz"), "No employees match.")


class DashboardLinkTests(TestCase):
    def test_dashboard_tiles_link_to_the_new_pages(self):
        make_user("hr_user", HR)
        make_user("alice", EMPLOYEE)
        self.client.login(username="alice", password=PASSWORD)
        page = self.client.get(reverse("dashboard-employee"))
        self.assertContains(page, reverse("attendance-home"))
        self.assertContains(page, reverse("leave-home"))
        self.assertNotContains(page, "Not available yet")
        self.client.logout()
        self.client.login(username="hr_user", password=PASSWORD)
        page = self.client.get(reverse("dashboard-hr"))
        for name in ("employees-home", "attendance-team", "leave-review"):
            self.assertContains(page, reverse(name))
        self.assertNotContains(page, "Not available yet")

    def test_navigation_shows_hr_links_only_to_hr(self):
        make_user("hr_user", HR)
        make_user("alice", EMPLOYEE)
        self.client.login(username="alice", password=PASSWORD)
        self.assertNotContains(self.client.get(reverse("dashboard-employee")), reverse("employees-home"))
        self.client.logout()
        self.client.login(username="hr_user", password=PASSWORD)
        self.assertContains(self.client.get(reverse("dashboard-hr")), reverse("employees-home"))
