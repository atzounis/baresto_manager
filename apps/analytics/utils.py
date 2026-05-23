from .models import AuditLog


def log_audit(user, action, target_type, target_id, delta=None, request=None):
    ip = None
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    AuditLog.objects.create(
        actor=user if user and user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        delta=delta or {},
        ip_address=ip,
    )
