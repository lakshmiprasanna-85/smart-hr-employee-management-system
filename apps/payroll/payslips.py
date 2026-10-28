"""Build payslip PDFs and store them against the payroll record."""
import io

from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.reports.models import AuditEvent
from apps.reports.services import record_event

from .models import SalaryComponent
from .notifications import notify_payslip_available
from .services import PayrollError

PLUM = colors.HexColor("#6f4a7e")
LINE = colors.HexColor("#d9d2ca")


def _inr(amount):
    return f"INR {amount:,.2f}"


def build_payslip_pdf(record):
    """Return the payslip for one payroll record as PDF bytes."""
    employee = record.employee
    user = employee.user
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], textColor=PLUM, alignment=0, fontSize=20)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#555555"))
    body = styles["Normal"]

    earnings = [l for l in record.lines.all() if l.component_type == SalaryComponent.ComponentType.EARNING]
    deductions = [l for l in record.lines.all() if l.component_type == SalaryComponent.ComponentType.DEDUCTION]

    def table(rows, total_label, total):
        data = [["Item", "Amount"]] + [[l.name, _inr(l.amount)] for l in rows] + [[total_label, _inr(total)]]
        t = Table(data, colWidths=[110 * mm, 55 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, PLUM),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.8, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return t

    info = Table(
        [
            ["Employee", user.get_full_name() or user.get_username(), "Employee no.", employee.employee_code],
            ["Department", str(employee.department or "-"), "Job title", employee.job_title or "-"],
            ["Pay period", record.period.label, "Generated on", timezone.localdate().strftime("%d %b %Y")],
        ],
        colWidths=[28 * mm, 57 * mm, 32 * mm, 48 * mm],
    )
    info.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    net = Table([["Net pay", _inr(record.net_amount)]], colWidths=[110 * mm, 55 * mm])
    net.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#efe6f2")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    story = [
        Paragraph("Smart HR - Payslip", title),
        Paragraph(f"Pay period {record.period.label}", small),
        Spacer(1, 8 * mm),
        info,
        Spacer(1, 8 * mm),
        Paragraph("<b>Earnings</b>", body),
        Spacer(1, 2 * mm),
        table(earnings, "Gross earnings", record.gross_amount),
        Spacer(1, 6 * mm),
        Paragraph("<b>Deductions</b>", body),
        Spacer(1, 2 * mm),
        table(deductions, "Total deductions", record.total_deductions),
        Spacer(1, 8 * mm),
        net,
        Spacer(1, 12 * mm),
        Paragraph(
            "This is a computer-generated payslip built from synthetic demo data. It is confidential: "
            "share it only with people who are allowed to see it.",
            small,
        ),
    ]
    buffer = io.BytesIO()
    # pageCompression=0 keeps the text readable in the file, which makes it testable.
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Payslip {record.period.label} {employee.employee_code}",
        author="Smart HR",
        pageCompression=0,
    ).build(story)
    return buffer.getvalue()


def generate_payslip(record, actor=None, notify=True):
    """
    Build the payslip PDF, store it on the record and tell the employee.

    The employee is emailed only the first time (not when a payslip is rebuilt).
    """
    if not record.lines.exists():
        raise PayrollError("This payroll record has no salary lines to put on a payslip.")

    first_time = not record.payslip_file
    if record.payslip_file:
        record.payslip_file.delete(save=False)
    # The file name is built from our own data only (never from user input).
    name = f"{record.period.label}-{record.employee.employee_code}.pdf"
    record.payslip_file.save(name, ContentFile(build_payslip_pdf(record)), save=False)
    record.payslip_generated_at = timezone.now()
    record.save(update_fields=["payslip_file", "payslip_generated_at", "updated_at"])

    record_event(
        actor,
        AuditEvent.Action.CREATE if first_time else AuditEvent.Action.UPDATE,
        "Payslip",
        record.pk,
        {"employee": record.employee.employee_code, "period": record.period.label},
    )
    if notify and first_time:
        notify_payslip_available(record)
    return record


def generate_payslips_for_period(period, actor=None, notify=True):
    """Create a payslip for every record in the period that has none. Returns how many were made."""
    created = 0
    for record in period.records.select_related("employee__user", "period").filter(payslip_file=""):
        generate_payslip(record, actor, notify=notify)
        created += 1
    return created
