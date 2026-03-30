from django.contrib.sessions.models import Session
from django.utils import timezone


def force_logout(user):
    active_sessions = Session.objects.filter(expire_date__gt=timezone.now())
    for session in active_sessions:
        data = session.get_decoded()
        if str(user.pk) == data.get("_auth_user_id"):
            session.delete()
