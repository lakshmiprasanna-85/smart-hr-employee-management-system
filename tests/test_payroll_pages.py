from django.test import TestCase
from django.urls import reverse

from apps.payroll.models import PayrollPeriod, PayrollRecord

from .test_payslips import PayslipTestCase
from .helpers import PASSWORD


class PayrollPagesTests(PayslipTestCase):
    def login(self, username):
        self.client.logout()
        self.client.login(username=username, password=PASSWORD)

    def test_hr_creates_a_period_from_the_form(self):
        self.login("hr_user")
        response = self.client.post(reverse("payroll-home"), {"year": 2026, "month": 10})
        period = PayrollPeriod.objects.get(year=2026, month=10)
        self.assertRedirects(response, reverse("payroll-period", kwargs={"pk": period.pk}))

    def test_bad_period_form_shows_an_error_message(self):
        self.login("hr_user")
        response = self.client.post(reverse("payroll-home"), {"year": "abc", "month": 10}, follow=True)
        self.assertContains(response, "Enter a valid year and month.")
        response = self.client.post(reverse("payroll-home"), {"year": 2026, "month": 9}, follow=True)
        self.assertContains(response, "already exists")

    def test_period_page_lists_records_for_hr(self):
        self.login("hr_user")
        response = self.client.get(reverse("payroll-period", kwargs={"pk": self.period.pk}))
        self.assertContains(response, "EMP001")
        self.assertContains(response, "EMP002")

    def test_period_page_forbidden_for_employee(self):
        self.login("alice")
        self.assertEqual(self.client.get(reverse("payroll-period", kwargs={"pk": self.period.pk})).status_code, 403)

    def test_action_endpoints_are_post_only_and_hr_only(self):
        pk = self.period.pk
        urls = [
            reverse("payroll-period-generate", kwargs={"pk": pk}),
            reverse("payroll-period-payslips", kwargs={"pk": pk}),
            reverse("payroll-period-close", kwargs={"pk": pk}),
            reverse("payroll-record-status", kwargs={"pk": self.alice_record.pk}),
            reverse("payroll-record-payslip", kwargs={"pk": self.alice_record.pk}),
        ]
        self.login("hr_user")
        for url in urls:
            with self.subTest(url=url, check="get not allowed"):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.login("alice")
        for url in urls:
            with self.subTest(url=url, check="employee forbidden"):
                self.assertEqual(self.client.post(url, {"status": "paid"}).status_code, 403)
        self.assertEqual(PayrollRecord.objects.get(pk=self.alice_record.pk).payment_status, "pending")

    def test_hr_generates_payslips_and_marks_paid_through_the_pages(self):
        self.login("hr_user")
        back = reverse("payroll-period", kwargs={"pk": self.period.pk})
        response = self.client.post(reverse("payroll-period-payslips", kwargs={"pk": self.period.pk}), follow=True)
        self.assertContains(response, "2 payslip(s) generated.")
        self.client.post(reverse("payroll-record-status", kwargs={"pk": self.alice_record.pk}), {"status": "paid"})
        self.assertEqual(PayrollRecord.objects.get(pk=self.alice_record.pk).payment_status, "paid")
        response = self.client.post(
            reverse("payroll-record-status", kwargs={"pk": self.alice_record.pk}), {"status": "pending"}, follow=True
        )
        self.assertRedirects(response, back)
        self.assertContains(response, "Cannot move a paid payroll record")

    def test_my_payslips_shows_only_own_records(self):
        self.login("alice")
        response = self.client.get(reverse("payroll-my"))
        self.assertContains(response, "2026-09")
        self.assertContains(response, "51000.00")  # Alice's net pay
        self.assertNotContains(response, "38200.00")  # Bob's net pay (30000 basic)

    def test_my_payslips_requires_login(self):
        response = self.client.get(reverse("payroll-my"))
        self.assertEqual(response.status_code, 302)
