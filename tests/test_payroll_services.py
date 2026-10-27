from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.payroll.models import (
    EmployeeSalaryComponent,
    PayrollPeriod,
    PayrollRecord,
    SalaryComponent,
)
from apps.payroll.services import (
    PayrollError,
    calculate_salary,
    close_period,
    create_period,
    generate_payroll,
    set_payment_status,
)
from apps.reports.models import AuditEvent

from .helpers import make_employee, make_period, make_user

EARN, DEDUCT = SalaryComponent.ComponentType.EARNING, SalaryComponent.ComponentType.DEDUCTION
PCT = SalaryComponent.CalculationType.PERCENT_OF_BASIC
Status = PayrollRecord.PaymentStatus


def give_salary(employee, basic="40000", hra_pct="40", pf_pct="12", tax="200"):
    """Basic + HRA (percent of basic) earnings; PF (percent) + tax (fixed) deductions."""
    components = [
        ("Basic", EARN, SalaryComponent.CalculationType.FIXED, basic),
        ("HRA", EARN, PCT, hra_pct),
        ("PF", DEDUCT, PCT, pf_pct),
        ("Professional Tax", DEDUCT, SalaryComponent.CalculationType.FIXED, tax),
    ]
    for name, kind, calc, value in components:
        component, _ = SalaryComponent.objects.get_or_create(
            name=name, defaults={"component_type": kind, "calculation_type": calc}
        )
        EmployeeSalaryComponent.objects.create(employee=employee, component=component, value=Decimal(value))


class CalculationTests(TestCase):
    def setUp(self):
        self.employee = make_employee(make_user("alice"), "EMP001")

    def test_percent_items_use_basic(self):
        give_salary(self.employee)
        lines = {name: amount for name, _, amount in calculate_salary(self.employee)}
        self.assertEqual(lines["Basic"], Decimal("40000.00"))
        self.assertEqual(lines["HRA"], Decimal("16000.00"))  # 40% of 40000
        self.assertEqual(lines["PF"], Decimal("4800.00"))  # 12% of 40000
        self.assertEqual(lines["Professional Tax"], Decimal("200.00"))

    def test_amounts_round_to_two_places(self):
        give_salary(self.employee, basic="33333.33", pf_pct="12")
        lines = {name: amount for name, _, amount in calculate_salary(self.employee)}
        self.assertEqual(lines["PF"], Decimal("4000.00"))  # 3999.9996 rounds to the paisa
        self.assertEqual(lines["HRA"], Decimal("13333.33"))  # 13333.332

    def test_no_components_is_an_error(self):
        with self.assertRaisesMessage(PayrollError, "No active salary components"):
            calculate_salary(self.employee)

    def test_percent_item_without_basic_is_an_error(self):
        hra = SalaryComponent.objects.create(name="HRA", component_type=EARN, calculation_type=PCT)
        EmployeeSalaryComponent.objects.create(employee=self.employee, component=hra, value=40)
        with self.assertRaisesMessage(PayrollError, "no Basic"):
            calculate_salary(self.employee)

    def test_deductions_cannot_exceed_earnings(self):
        give_salary(self.employee, basic="1000", tax="5000")
        with self.assertRaisesMessage(PayrollError, "larger than earnings"):
            calculate_salary(self.employee)

    def test_inactive_component_is_ignored(self):
        give_salary(self.employee)
        SalaryComponent.objects.filter(name="Professional Tax").update(is_active=False)
        names = [name for name, _, _ in calculate_salary(self.employee)]
        self.assertNotIn("Professional Tax", names)


class PeriodTests(TestCase):
    def test_create_period_derives_dates(self):
        period = create_period(2026, 2)
        self.assertEqual((period.start_date, period.end_date), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_duplicate_period_rejected(self):
        create_period(2026, 9)
        with self.assertRaises(PayrollError):
            create_period(2026, 9)

    def test_invalid_month_rejected(self):
        with self.assertRaises(PayrollError):
            create_period(2026, 13)

    def test_cannot_close_with_pending_records(self):
        employee = make_employee(make_user("alice"), "EMP001")
        give_salary(employee)
        period = make_period()
        generate_payroll(period)
        with self.assertRaisesMessage(PayrollError, "still pending"):
            close_period(period)

    def test_close_period_after_all_paid_and_audited(self):
        admin = make_user("boss", User.Role.ADMIN)
        employee = make_employee(make_user("alice"), "EMP001")
        give_salary(employee)
        period = make_period()
        generate_payroll(period, admin)
        set_payment_status(period.records.get(), Status.PAID, admin)
        close_period(period, admin)
        period.refresh_from_db()
        self.assertEqual(period.status, PayrollPeriod.Status.CLOSED)
        self.assertTrue(
            AuditEvent.objects.filter(entity_type="PayrollPeriod", action="status_change", actor=admin).exists()
        )

    def test_cannot_close_twice(self):
        period = make_period()
        close_period(period)
        with self.assertRaises(PayrollError):
            close_period(period)


class GenerationTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", User.Role.ADMIN)
        self.alice = make_employee(make_user("alice"), "EMP001")
        self.bob = make_employee(make_user("bob"), "EMP002")
        give_salary(self.alice)
        self.period = make_period()

    def test_creates_record_with_totals_and_line_snapshot(self):
        summary = generate_payroll(self.period, self.admin)
        self.assertEqual(summary["created"], 1)
        record = PayrollRecord.objects.get(employee=self.alice, period=self.period)
        self.assertEqual(record.gross_amount, Decimal("56000.00"))
        self.assertEqual(record.total_deductions, Decimal("5000.00"))
        self.assertEqual(record.net_amount, Decimal("51000.00"))
        self.assertEqual(record.lines.count(), 4)

    def test_employee_without_salary_setup_is_not_on_payroll(self):
        generate_payroll(self.period)
        self.assertFalse(PayrollRecord.objects.filter(employee=self.bob).exists())

    def test_running_twice_creates_no_duplicates(self):
        generate_payroll(self.period)
        summary = generate_payroll(self.period)
        self.assertEqual(summary["created"], 0)
        self.assertEqual(summary["unchanged"], 1)
        self.assertEqual(PayrollRecord.objects.count(), 1)

    def test_changed_salary_updates_unpaid_record_and_audits_it(self):
        generate_payroll(self.period, self.admin)
        EmployeeSalaryComponent.objects.filter(employee=self.alice, component__name="Basic").update(value=50000)
        summary = generate_payroll(self.period, self.admin)
        self.assertEqual(summary["updated"], 1)
        record = PayrollRecord.objects.get()
        self.assertEqual(record.gross_amount, Decimal("70000.00"))
        event = AuditEvent.objects.filter(entity_type="PayrollRecord", action="update").get()
        self.assertEqual(event.changes["net_before"], "51000.00")
        self.assertEqual(event.changes["net_after"], "63800.00")

    def test_paid_record_is_never_changed(self):
        generate_payroll(self.period)
        set_payment_status(PayrollRecord.objects.get(), Status.PAID)
        EmployeeSalaryComponent.objects.filter(employee=self.alice, component__name="Basic").update(value=90000)
        summary = generate_payroll(self.period)
        self.assertEqual(summary["skipped_paid"], 1)
        self.assertEqual(PayrollRecord.objects.get().gross_amount, Decimal("56000.00"))

    def test_closed_period_cannot_be_generated(self):
        self.period.status = PayrollPeriod.Status.CLOSED
        self.period.save()
        with self.assertRaisesMessage(PayrollError, "closed"):
            generate_payroll(self.period)

    def test_unfixable_employee_is_reported_not_hidden(self):
        give_salary(self.bob, basic="1000", tax="9000")
        summary = generate_payroll(self.period)
        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["errors"][0][0], "EMP002")

    def test_terminated_employee_is_skipped(self):
        self.alice.employment_status = "terminated"
        self.alice.save()
        self.assertEqual(generate_payroll(self.period)["created"], 0)

    def test_creation_is_audited(self):
        generate_payroll(self.period, self.admin)
        self.assertTrue(
            AuditEvent.objects.filter(entity_type="PayrollRecord", action="create", actor=self.admin).exists()
        )


class PaymentStatusTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", User.Role.ADMIN)
        employee = make_employee(make_user("alice"), "EMP001")
        give_salary(employee)
        generate_payroll(make_period())
        self.record = PayrollRecord.objects.get()

    def test_pending_to_paid_sets_date_and_audits(self):
        set_payment_status(self.record, Status.PAID, self.admin, paid_on=date(2026, 9, 30))
        self.record.refresh_from_db()
        self.assertEqual((self.record.payment_status, self.record.paid_on), (Status.PAID, date(2026, 9, 30)))
        event = AuditEvent.objects.get(entity_type="PayrollRecord", action="status_change")
        self.assertEqual((event.changes["from"], event.changes["to"]), ("pending", "paid"))

    def test_hold_and_release(self):
        set_payment_status(self.record, Status.ON_HOLD, self.admin)
        set_payment_status(self.record, Status.PENDING, self.admin)
        self.assertEqual(self.record.payment_status, Status.PENDING)

    def test_paid_is_final(self):
        set_payment_status(self.record, Status.PAID, self.admin)
        for target in (Status.PENDING, Status.ON_HOLD, Status.PAID):
            with self.subTest(target=target), self.assertRaises(PayrollError):
                set_payment_status(self.record, target, self.admin)
