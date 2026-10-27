from apps.reports.notifications import send_notification


def notify_payslip_available(record):
    """Tell the employee a payslip is ready. The email never contains salary figures."""
    return send_notification(
        "payslip_available",
        record.employee.user,
        f"Your payslip for {record.period.label} is ready",
        "emails/payslip_available.txt",
        {"period": record.period.label},
    )
