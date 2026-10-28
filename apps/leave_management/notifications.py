from apps.reports.notifications import send_notification

from .states import LeaveStatus


def notify_leave_decision(leave_request):
    """Tell the employee that their request was approved or rejected."""
    if leave_request.status not in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        return None
    decision = leave_request.get_status_display().lower()
    return send_notification(
        "leave_decision",
        leave_request.employee.user,
        f"Your leave request was {decision}",
        "emails/leave_decision.txt",
        {
            "leave_type": leave_request.leave_type.name,
            "start_date": leave_request.start_date,
            "end_date": leave_request.end_date,
            "days": leave_request.total_days,
            "decision": decision,
            "note": leave_request.reviewer_note,
        },
    )
