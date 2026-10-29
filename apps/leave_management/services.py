"""Leave approval rules: enforce the state machine and keep a status history."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User

from .models import LeaveStatusHistory
from .notifications import notify_leave_decision
from .states import LeaveStatus, can_transition


class LeaveTransitionError(Exception):
    """Raised when a requested status change is not allowed."""


class LeavePermissionError(Exception):
    """Raised when this user may not make the requested decision."""


def check_decision_allowed(user, leave_request, to_status):
    """
    Who may do what (shared by the API and the web pages).

    * Only Admin/HR may approve or reject, and never their own request.
    * The owner (or Admin/HR) may cancel.
    """
    is_privileged = user.role in (User.Role.ADMIN, User.Role.HR)
    is_owner = leave_request.employee.user_id == user.id
    if to_status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        if is_owner:
            raise LeavePermissionError("You cannot approve or reject your own leave request.")
        if not is_privileged:
            raise LeavePermissionError("Only Admin or HR may decide this request.")
    if to_status == LeaveStatus.CANCELLED and not (is_privileged or is_owner):
        raise LeavePermissionError("You may only cancel your own request.")


def process_decision(user, leave_request, to_status, note=""):
    """Check permission, move the request, then email the employee about approvals/rejections."""
    check_decision_allowed(user, leave_request, to_status)
    decide(leave_request, to_status, user, note)
    # Sent after the decision is saved; an email problem never undoes the decision.
    notify_leave_decision(leave_request)
    return leave_request


@transaction.atomic
def decide(leave_request, to_status, user, note=""):
    """
    Move a leave request to `to_status`, recording who did it and why.

    Raises LeaveTransitionError when the state machine forbids the move.
    """
    if not can_transition(leave_request.status, to_status):
        raise LeaveTransitionError(
            f"Cannot move a {leave_request.status} request to {to_status}."
        )

    from_status = leave_request.status
    leave_request.status = to_status
    if to_status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        leave_request.reviewed_by = user
        leave_request.decided_at = timezone.now()
    leave_request.reviewer_note = note
    leave_request.save()

    LeaveStatusHistory.objects.create(
        leave_request=leave_request,
        from_status=from_status,
        to_status=to_status,
        changed_by=user,
        note=note,
    )
    return leave_request
