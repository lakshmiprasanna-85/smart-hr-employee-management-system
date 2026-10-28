import shutil
import tempfile

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.payroll.models import EmployeeSalaryComponent, PayrollRecord
from apps.payroll.payslips import build_payslip_pdf, generate_payslip, generate_payslips_for_period
from apps.payroll.services import PayrollError, generate_payroll
from apps.reports.models import AuditEvent, NotificationLog

from .helpers import PASSWORD, make_employee, make_period, make_user
from .test_payroll_services import give_salary

ADMIN, HR, EMPLOYEE = User.Role.ADMIN, User.Role.HR, User.Role.EMPLOYEE


class PayslipTestCase(TestCase):
    """Base class: a temporary MEDIA_ROOT so tests never write into the project folder."""

    def setUp(self):
        media = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, media, True)

        self.admin = make_user("boss", ADMIN)
        self.hr = make_user("hr_user", HR)
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")
        self.bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        give_salary(self.alice)
        give_salary(self.bob, basic="30000")
        self.period = make_period()
        generate_payroll(self.period, self.admin)
        self.alice_record = PayrollRecord.objects.get(employee=self.alice)
        self.bob_record = PayrollRecord.objects.get(employee=self.bob)


class PayslipGenerationTests(PayslipTestCase):
    def test_pdf_contains_the_employee_and_amounts(self):
        pdf = build_payslip_pdf(self.alice_record)
        self.assertTrue(pdf.startswith(b"%PDF"))
        for text in (b"EMP001", b"2026-09", b"INR 51,000.00", b"Basic", b"PF"):
            self.assertIn(text, pdf)
        self.assertNotIn(b"EMP002", pdf)

    def test_generate_stores_file_audits_and_emails_once(self):
        generate_payslip(self.alice_record, self.admin)
        self.alice_record.refresh_from_db()
        self.assertTrue(self.alice_record.payslip_file.name.endswith("2026-09-EMP001.pdf"))
        self.assertIsNotNone(self.alice_record.payslip_generated_at)
        self.assertTrue(AuditEvent.objects.filter(entity_type="Payslip", action="create", actor=self.admin).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])

        generate_payslip(self.alice_record, self.admin)  # rebuilding does not email again
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(AuditEvent.objects.filter(entity_type="Payslip", action="update").exists())

    def test_generate_for_period_skips_existing_payslips(self):
        generate_payslip(self.alice_record, self.admin)
        self.assertEqual(generate_payslips_for_period(self.period, self.admin), 1)  # only Bob's
        self.assertEqual(generate_payslips_for_period(self.period, self.admin), 0)

    def test_failed_email_does_not_block_the_payslip(self):
        from unittest import mock

        with mock.patch("apps.reports.notifications.send_mail", side_effect=OSError("down")):
            generate_payslip(self.alice_record, self.admin)
        self.alice_record.refresh_from_db()
        self.assertTrue(self.alice_record.payslip_file)
        self.assertEqual(NotificationLog.objects.get().status, "failed")

    def test_record_without_lines_cannot_have_a_payslip(self):
        self.alice_record.lines.all().delete()
        with self.assertRaises(PayrollError):
            generate_payslip(self.alice_record)

    def test_changed_salary_discards_the_old_payslip(self):
        generate_payslip(self.alice_record, self.admin)
        EmployeeSalaryComponent.objects.filter(employee=self.alice, component__name="Basic").update(value=45000)
        generate_payroll(self.period, self.admin)
        self.alice_record.refresh_from_db()
        self.assertFalse(self.alice_record.payslip_file)
        self.assertIsNone(self.alice_record.payslip_generated_at)


class PayslipDownloadTests(PayslipTestCase):
    def setUp(self):
        super().setUp()
        generate_payslip(self.alice_record, self.admin)
        generate_payslip(self.bob_record, self.admin)
        self.url = reverse("payslip-download", kwargs={"pk": self.alice_record.pk})

    def _get(self, username, url=None):
        self.client.login(username=username, password=PASSWORD)
        return self.client.get(url or self.url)

    def test_owner_downloads_own_payslip(self):
        response = self._get("alice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("payslip-2026-09-EMP001.pdf", response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_employee_cannot_download_a_colleagues_payslip(self):
        self.assertEqual(self._get("bob").status_code, 404)

    def test_hr_and_admin_can_download_any_payslip(self):
        for username in ("hr_user", "boss"):
            with self.subTest(user=username):
                self.assertEqual(self._get(username).status_code, 200)
                self.client.logout()

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_missing_payslip_is_404(self):
        PayrollRecord.objects.filter(pk=self.alice_record.pk).update(payslip_file="")
        self.assertEqual(self._get("alice").status_code, 404)

    def test_missing_file_on_disk_is_404(self):
        self.alice_record.payslip_file.delete(save=False)
        self.assertEqual(self._get("alice").status_code, 404)

    def test_unknown_record_is_404(self):
        self.assertEqual(self._get("alice", reverse("payslip-download", kwargs={"pk": 9999})).status_code, 404)

    def test_files_are_not_served_from_a_public_media_url(self):
        name = self.alice_record.payslip_file.name
        self.client.login(username="boss", password=PASSWORD)
        self.assertEqual(self.client.get(f"/media/{name}").status_code, 404)
