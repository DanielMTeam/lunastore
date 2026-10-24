from constance import config
from django.db.models import F

from .models import Ticket


def support_context(request):
    enabled = config.SUPPORT_ENABLED
    count = 0
    if enabled and getattr(request, 'user', None) and request.user.is_authenticated:
        count = Ticket.objects.filter(owner=request.user, last_staff_message_id__gt=F('owner_read_message_id')).count()
    return {'support_enabled': enabled, 'support_unread_count': count}
