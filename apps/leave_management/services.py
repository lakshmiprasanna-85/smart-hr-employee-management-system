"""Leave approval rules: enforce the state machine and keep a status history."""
from django.db import transaction
from django.utils import timezone

from .models import LeaveStatusHistory
from .states import LeaveStatus, can_transition


class LeaveTransitionError(Exception):
    """Raised when a requested status change is not allowed."""


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
