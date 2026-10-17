import logging

from .models import AuditEvent

logger = logging.getLogger(__name__)


def record_event(actor, action, entity_type, entity_id="", changes=None):
    """Write one audit event. Call this from any view/service that changes sensitive data."""
    event = AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        changes=changes or {},
    )
    logger.info("audit %s %s#%s by %s", action, entity_type, entity_id, actor)
    return event
