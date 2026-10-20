"""
Leave request states and the allowed transitions between them.

This module has no Django model imports so it can be used anywhere
(models, views, serializers, tests).

    PENDING  -> APPROVED | REJECTED | CANCELLED
    APPROVED -> CANCELLED
    REJECTED -> (final)
    CANCELLED -> (final)
"""
from django.db import models


class LeaveStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


ALLOWED_TRANSITIONS = {
    LeaveStatus.PENDING: {LeaveStatus.APPROVED, LeaveStatus.REJECTED, LeaveStatus.CANCELLED},
    LeaveStatus.APPROVED: {LeaveStatus.CANCELLED},
    LeaveStatus.REJECTED: set(),
    LeaveStatus.CANCELLED: set(),
}


def can_transition(from_status, to_status):
    """Return True if a leave request may move from `from_status` to `to_status`."""
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())
