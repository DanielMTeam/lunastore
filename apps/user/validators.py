import re 
from django.core.exceptions import ValidationError
from .models import BlacklistedUsername
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import User

def validate_username_blacklist(value):
    low_value = value.lower()
    blacklist = BlacklistedUsername.objects.all()
    
    for item in blacklist:
        if item.is_regex:
            if re.search(item.word, low_value):
                raise ValidationError(f'Nickname containce ban-pattern: {item.word}')
        elif item.word.lower() in low_value:
            raise ValidationError('Nickname containcs ban-word(-s)')

def validate_invite_limit(owner):
    time_threshold = timezone.now() - timedelta(days=settings.MAX_INVITE_DAYS_LIMIT)
    
    recent_invites_count = User.objects.filter(
        invited_by = owner,
        date_joined__gte=time_threshold
    ).count()
    
    if recent_invites_count >= settings.MAX_INVITE_USES_COUNT:
        return False
    return True