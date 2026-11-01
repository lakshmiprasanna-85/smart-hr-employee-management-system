"""Downloadable reports (CSV, Excel and PDF) for Admin and HR.

Every report is read-only. Personal fields (phone, date of birth, address) are
never exported, and text cells are guarded against spreadsheet formula
injection before they reach CSV or Excel.
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from django.utils import timezone

from apps.attendance.models import Attendance
from apps.employees.models import Employee
from apps.leave_management.models import LeaveRequest
from apps.payroll.models import PayrollPeriod

from .kpis import month_label, year_month

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
EXTENSIONS = {"csv": "csv", "xlsx": "xlsx", "pdf": "pdf"}

# A spreadsheet treats a cell beginning with one of these characters as a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_text(value):
    """Neutralise spreadsheet formulas without changing how the text reads."""
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _name(employee):
    return employee.user.get_full_name().strip() or employee.user.get_username()


def _clock(value):
    return timezone.localtime(value).strftime("%H:%M") if value else "-"


def _date(value):
    return value.isoformat() if value else "-"


def _text(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


def _display(value, numeric=False):
    """Human-readable text for CSV/PDF cells (Excel keeps real numbers instead)."""
    if isinstance(value, Decimal):
        return f"{value:.2f}" if numeric else str(value)
    if isinstance(value, float) and numeric:
        return f"{value:.2f}"
    return str(value)


# --------------------------------------------------------------------------
# Row sources
# --------------------------------------------------------------------------
def _employees(params):
    rows = [
        [
            employee.employee_code,
            _name(employee),
            employee.department.name if employee.department else "No department",
            employee.job_title or "-",
            employee.get_employment_status_display(),
            _date(employee.joining_date),
        ]
        for employee in Employee.objects.select_related("user", "department").order_by(
            "employee_code"
        )
    ]
    return {
        "title": "Employee directory",
        "subtitle": "All employee records, including former employees. Personal contact details are not included.",
        "columns": ["Employee no.", "Name", "Department", "Job title", "Status", "Joined"],
        "rows": rows,
        "numeric": set(),
        "filename": f"employees-{timezone.localdate().isoformat()}",
        "filters": {},
    }


def _attendance(params):
    year, month = year_month(params.get("year"), params.get("month"))
    rows = [
        [
            record.employee.employee_code,
            _name(record.employee),
            _date(record.date),
            _clock(record.check_in),
            _clock(record.check_out),
            record.get_status_display(),
        ]
        for record in Attendance.objects.filter(date__year=year, date__month=month)
        .select_related("employee__user")
        .order_by("date", "employee__employee_code")
    ]
    return {
        "title": "Attendance",
        "subtitle": f"All attendance records for {month_label(year, month)}.",
        "columns": ["Employee no.", "Employee", "Date", "Check in", "Check out", "Status"],
        "rows": rows,
        "numeric": set(),
        "filename": f"attendance-{year}-{month:02d}",
        "filters": {"year": year, "month": month},
    }


def _leave(params):
    year, month = year_month(params.get("year"), params.get("month"))
    rows = [
        [
            request.employee.employee_code,
            _name(request.employee),
            request.leave_type.name,
            _date(request.start_date),
            _date(request.end_date),
            request.total_days,
            request.get_status_display(),
        ]
        for request in LeaveRequest.objects.filter(
            start_date__year=year, start_date__month=month
        )
        .select_related("employee__user", "leave_type")
        .order_by("start_date", "employee__employee_code")
    ]
    return {
        "title": "Leave requests",
        "subtitle": f"Leave requests starting in {month_label(year, month)}.",
        "columns": ["Employee no.", "Employee", "Leave type", "Start", "End", "Days", "Status"],
        "rows": rows,
        "numeric": {5},
        "filename": f"leave-{year}-{month:02d}",
        "filters": {"year": year, "month": month},
    }


def _payroll(params):
    year, month = year_month(params.get("year"), params.get("month"))
    period = PayrollPeriod.objects.filter(year=year, month=month).first()
    note = ""
    if period is None:
        period = PayrollPeriod.objects.order_by("-year", "-month").first()
        note = f" No payroll period exists for {year}-{month:02d}; the latest period is shown."
    rows = []
    if period is not None:
        rows = [
            [
                period.label,
                record.employee.employee_code,
                _name(record.employee),
                record.gross_amount,
                record.total_deductions,
                record.net_amount,
                record.get_payment_status_display(),
                _date(record.paid_on),
            ]
            for record in period.records.select_related("employee__user").order_by(
                "employee__employee_code"
            )
        ]
    return {
        "title": "Payroll",
        "subtitle": (
            f"Payroll records for {period.label}.{note}"
            if period is not None
            else "No payroll period has been created yet."
        ),
        "columns": [
            "Period",
            "Employee no.",
            "Employee",
            "Gross",
            "Deductions",
            "Net",
            "Payment status",
            "Paid on",
        ],
        "rows": rows,
        "numeric": {3, 4, 5},
        "filename": f"payroll-{period.label}" if period is not None else "payroll-empty",
        "filters": {
            "year": year,
            "month": month,
            "period": period.label if period is not None else "",
        },
    }


REPORT_BUILDERS = {
    "employees": _employees,
    "attendance": _attendance,
    "leave": _leave,
    "payroll": _payroll,
}


def build_report(kind, params):
    """Build one report. Raises KeyError for an unknown report name."""
    return REPORT_BUILDERS[kind](params)


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def to_csv(report):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(report["columns"])
    for row in report["rows"]:
        writer.writerow(
            [
                safe_text(_display(value, index in report["numeric"]))
                for index, value in enumerate(row)
            ]
        )
    # The BOM makes Excel open the UTF-8 file with the right encoding.
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------
def to_xlsx(report):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = report["title"][:31]
    sheet.sheet_view.showGridLines = False

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="6F4A7E")
    for column, name in enumerate(report["columns"], start=1):
        cell = sheet.cell(row=1, column=column, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")

    for row_number, row in enumerate(report["rows"], start=2):
        for column, value in enumerate(row, start=1):
            if (column - 1) in report["numeric"] and isinstance(value, (int, float, Decimal)):
                sheet.cell(row=row_number, column=column, value=float(value))
            else:
                sheet.cell(row=row_number, column=column, value=safe_text(_display(value)))

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in range(1, len(report["columns"]) + 1):
        longest = max(
            [len(str(report["columns"][column - 1]))]
            + [len(_display(row[column - 1])) for row in report["rows"]]
        )
        sheet.column_dimensions[get_column_letter(column)].width = min(max(longest + 2, 10), 40)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def to_pdf(report, actor_name=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=report["title"],
        author="Smart HR",
    )

    title_style = ParagraphStyle(
        "ReportTitle",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#2b2a3a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#6a6879"),
    )
    header_style = ParagraphStyle(
        "ReportHeader", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white
    )
    cell_style = ParagraphStyle("ReportCell", fontName="Helvetica", fontSize=7.5, leading=9)
    footer_style = ParagraphStyle(
        "ReportFooter",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#6a6879"),
    )

    story = [
        Paragraph(escape(report["title"]), title_style),
        Paragraph(escape(report["subtitle"]), subtitle_style),
        Spacer(1, 5 * mm),
    ]

    table_data = [
        [Paragraph(escape(str(column)), header_style) for column in report["columns"]]
    ]
    for row in report["rows"]:
        table_data.append(
            [
                Paragraph(
                    escape(_display(value, index in report["numeric"])),
                    cell_style,
                )
                for index, value in enumerate(row)
            ]
        )

    available = landscape(A4)[0] - 24 * mm
    widths = [available / len(report["columns"])] * len(report["columns"])
    table = LongTable(table_data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6f4a7e")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ebe5de")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf7f3")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    generated = timezone.localtime().strftime("%d %b %Y %H:%M")
    story.append(
        Paragraph(
            escape(
                f"Generated by {actor_name or 'Smart HR'} on {generated} · "
                f"{len(report['rows'])} row(s)"
            ),
            footer_style,
        )
    )
    document.build(story)
    return buffer.getvalue()


def render_export(report, fmt, actor_name=""):
    """Render a report in one format. Raises KeyError for an unknown format."""
    if fmt == "csv":
        return to_csv(report)
    if fmt == "xlsx":
        return to_xlsx(report)
    if fmt == "pdf":
        return to_pdf(report, actor_name)
    raise KeyError(fmt)
