"""Send an email and keep a NotificationLog row for every attempt."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import NotificationLog

logger = logging.getLogger(__name__)


def send_notification(notification_type, user, subject, template, context=None):
    """
    Email `user` using a plain-text template and log the outcome.

    This never raises: a mail-server problem must not break the action that
    triggered the email (a leave decision, a payslip). Failures are stored in the
    log with the error message, so they can be counted and retried.
    """
    email = (getattr(user, "email", "") or "").strip()
    log = NotificationLog.objects.create(
        notification_type=notification_type,
        recipient=user,
        recipient_email=email,
        subject=subject,
    )
    if not email:
        log.status = NotificationLog.Status.FAILED
        log.error_message = "The user has no email address."
        log.save(update_fields=["status", "error_message"])
        logger.warning("notification %s not sent: user %s has no email", notification_type, user)
        return log

    try:
        body = render_to_string(template, {"user": user, "site_url": settings.SITE_URL, **(context or {})})
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as exc:  # noqa: BLE001 - any mail failure must be logged, not raised
        log.status = NotificationLog.Status.FAILED
        log.error_message = f"{type(exc).__name__}: {exc}"[:1000]
        log.save(update_fields=["status", "error_message"])
        logger.warning("notification %s to %s failed: %s", notification_type, email, exc)
    else:
        log.status = NotificationLog.Status.SENT
        log.sent_at = timezone.now()
        log.save(update_fields=["status", "sent_at"])
    return log
