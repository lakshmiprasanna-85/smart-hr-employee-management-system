from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import AuditEvent
from .services import record_event


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    record_event(user, AuditEvent.Action.LOGIN, "User", user.pk)


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request=None, **kwargs):
    """Record a failed login attempt. The password is never stored."""
    username = str(credentials.get("username", ""))[:150]
    record_event(
        None,
        AuditEvent.Action.LOGIN,
        "User",
        "",
        {"result": "failed", "username": username},
    )
