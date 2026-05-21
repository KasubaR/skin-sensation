from django.contrib.auth import get_user_model

from dashboard.models import StaffActivityLog

User = get_user_model()


def log_staff_activity(
  *,
  user: User,
  action: str,
  message: str,
  target_type: str = '',
  target_id: str = '',
) -> StaffActivityLog:
  return StaffActivityLog.objects.create(
    user=user,
    action=action,
    message=message,
    target_type=target_type,
    target_id=target_id,
  )


def get_recent_activity(limit: int = 10):
  return StaffActivityLog.objects.select_related('user').order_by('-created_at')[:limit]
