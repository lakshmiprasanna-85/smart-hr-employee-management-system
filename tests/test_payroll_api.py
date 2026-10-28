import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.payroll.models import EmployeeSalaryComponent, PayrollRecord, SalaryComponent
from apps.reports.models import AuditEvent

from .helpers import PASSWORD, make_employee, make_period, make_user
from .test_payroll_services import give_salary

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE


class PayrollApiTestCase(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, media, True)
        self.admin = make_user("boss", ADMIN)
        self.hr = make_user("hr_user", HR)
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")

    def login(self, username):
        self.client.logout()
        self.client.login(username=username, password=PASSWORD)

    def post(self, name, data=None, **kwargs):
        return self.client.post(reverse(name, kwargs=kwargs), data or {}, content_type="application/json")


class PeriodApiTests(PayrollApiTestCase):
    def test_hr_creates_period_and_dates_are_derived(self):
        self.login("hr_user")
        response = self.post("api-payroll-periods", {"year": 2026, "month": 10})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["start_date"], "2026-10-01")
        self.assertEqual(response.json()["end_date"], "2026-10-31")
        self.assertTrue(AuditEvent.objects.filter(entity_type="PayrollPeriod", action="create").exists())

    def test_duplicate_and_bad_month_rejected(self):
        self.login("hr_user")
        self.post("api-payroll-periods", {"year": 2026, "month": 10})
        self.assertEqual(self.post("api-payroll-periods", {"year": 2026, "month": 10}).status_code, 400)
        self.assertEqual(self.post("api-payroll-periods", {"year": 2026, "month": 13}).status_code, 400)

    def test_employee_and_anonymous_cannot_use_period_endpoints(self):
        period = make_period()
        self.assertEqual(self.client.get(reverse("api-payroll-periods")).status_code, 403)
        self.login("alice")
        self.assertEqual(self.client.get(reverse("api-payroll-periods")).status_code, 403)
        for name in ("api-payroll-generate", "api-payroll-payslips", "api-payroll-close"):
            with self.subTest(endpoint=name):
                self.assertEqual(self.post(name, pk=period.pk).status_code, 403)

    def test_generate_then_payslips_then_pay_then_close(self):
        give_salary(self.alice)
        period = make_period()
        self.login("hr_user")

        result = self.post("api-payroll-generate", pk=period.pk).json()
        self.assertEqual(result["created"], 1)

        self.assertEqual(self.post("api-payroll-close", pk=period.pk).status_code, 409)  # still pending

        self.assertEqual(self.post("api-payroll-payslips", pk=period.pk).json()["payslips_generated"], 1)

        record = PayrollRecord.objects.get()
        paid = self.post("api-payroll-record-status", {"status": "paid"}, pk=record.pk)
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(paid.json()["payment_status"], "paid")
        self.assertEqual(self.post("api-payroll-record-status", {"status": "pending"}, pk=record.pk).status_code, 409)

        self.assertEqual(self.post("api-payroll-close", pk=period.pk).json()["status"], "closed")
        self.assertEqual(self.post("api-payroll-generate", pk=period.pk).status_code, 409)  # closed

    def test_employee_cannot_change_payment_status(self):
        give_salary(self.alice)
        period = make_period()
        self.login("hr_user")
        self.post("api-payroll-generate", pk=period.pk)
        record = PayrollRecord.objects.get()
        self.login("alice")
        self.assertEqual(self.post("api-payroll-record-status", {"status": "paid"}, pk=record.pk).status_code, 403)

    def test_invalid_status_value_rejected(self):
        give_salary(self.alice)
        period = make_period()
        self.login("hr_user")
        self.post("api-payroll-generate", pk=period.pk)
        record = PayrollRecord.objects.get()
        self.assertEqual(self.post("api-payroll-record-status", {"status": "banana"}, pk=record.pk).status_code, 400)

    def test_records_can_be_filtered_by_period(self):
        give_salary(self.alice)
        sept, octo = make_period(2026, 9), make_period(2026, 10)
        self.login("hr_user")
        self.post("api-payroll-generate", pk=sept.pk)
        self.post("api-payroll-generate", pk=octo.pk)
        response = self.client.get(reverse("api-payroll-records") + "?period=2026-10")
        self.assertEqual([row["period"] for row in response.json()], ["2026-10"])
        self.assertEqual(self.client.get(reverse("api-payroll-records") + "?period=oops").json(), [])


class SalaryApiTests(PayrollApiTestCase):
    def test_hr_manages_components_and_audits(self):
        self.login("hr_user")
        created = self.post(
            "api-salary-components",
            {"name": "Basic", "component_type": "earning", "calculation_type": "fixed", "default_value": "30000"},
        )
        self.assertEqual(created.status_code, 201)
        self.assertTrue(AuditEvent.objects.filter(entity_type="SalaryComponent", action="create").exists())
        patched = self.client.patch(
            reverse("api-salary-component", kwargs={"pk": created.json()["id"]}),
            {"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertFalse(SalaryComponent.objects.get().is_active)

    def test_percentage_over_100_and_negative_values_rejected(self):
        self.login("hr_user")
        base = {"component_type": "earning", "calculation_type": "percent_of_basic"}
        self.assertEqual(self.post("api-salary-components", {**base, "name": "HRA", "default_value": "150"}).status_code, 400)
        self.assertEqual(self.post("api-salary-components", {**base, "name": "HRA", "default_value": "-5"}).status_code, 400)

    def test_employee_cannot_read_or_change_salary_setup(self):
        give_salary(self.alice)
        self.login("alice")
        self.assertEqual(self.client.get(reverse("api-salary-components")).status_code, 403)
        self.assertEqual(self.client.get(reverse("api-employee-salary")).status_code, 403)
        row = EmployeeSalaryComponent.objects.first()
        self.assertEqual(self.client.get(reverse("api-employee-salary-detail", kwargs={"pk": row.pk})).status_code, 403)
        self.assertEqual(
            self.client.patch(
                reverse("api-employee-salary-detail", kwargs={"pk": row.pk}), {"value": "999999"}, content_type="application/json"
            ).status_code,
            403,
        )

    def test_assign_update_and_remove_employee_salary_with_audit(self):
        basic = SalaryComponent.objects.create(name="Basic", component_type="earning")
        self.login("hr_user")
        created = self.post("api-employee-salary", {"employee": self.alice.pk, "component": basic.pk, "value": "30000"})
        self.assertEqual(created.status_code, 201)
        pk = created.json()["id"]
        url = reverse("api-employee-salary-detail", kwargs={"pk": pk})

        updated = self.client.patch(url, {"value": "35000"}, content_type="application/json")
        self.assertEqual(updated.status_code, 200)
        event = AuditEvent.objects.get(entity_type="EmployeeSalaryComponent", action="update")
        self.assertEqual((event.changes["before"], event.changes["after"]), ("30000.00", "35000.00"))
        self.assertEqual(event.actor, self.hr)

        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertTrue(AuditEvent.objects.filter(entity_type="EmployeeSalaryComponent", action="delete").exists())

    def test_same_component_cannot_be_assigned_twice(self):
        basic = SalaryComponent.objects.create(name="Basic", component_type="earning")
        self.login("hr_user")
        payload = {"employee": self.alice.pk, "component": basic.pk, "value": "30000"}
        self.post("api-employee-salary", payload)
        self.assertEqual(self.post("api-employee-salary", payload).status_code, 400)

    def test_inactive_component_cannot_be_assigned(self):
        old = SalaryComponent.objects.create(name="Old", component_type="earning", is_active=False)
        self.login("hr_user")
        response = self.post("api-employee-salary", {"employee": self.alice.pk, "component": old.pk, "value": "1"})
        self.assertEqual(response.status_code, 400)

    def test_filter_salary_rows_by_employee(self):
        give_salary(self.alice)
        bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        give_salary(bob)
        self.login("hr_user")
        rows = self.client.get(reverse("api-employee-salary") + f"?employee={bob.pk}").json()
        self.assertEqual({row["employee_code"] for row in rows}, {"EMP002"})
