import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import BlacklistedUsername, User


def validate_username_blacklist(value):
    low_value = value.lower()
    blacklist = BlacklistedUsername.objects.all()

    for item in blacklist:
        if item.is_regex:
            if re.search(item.word, low_value):
                raise ValidationError(f"Nickname containce ban-pattern: {item.word}")
        elif item.word.lower() in low_value:
            raise ValidationError("Nickname containcs ban-word(-s)")


def validate_invite_limit(owner):
    time_threshold = timezone.now() - timedelta(
        days=int(settings.MAX_INVITE_DAYS_LIMIT)
    )

<<<<<<< HEAD
=======
    
>>>>>>> fd172f14a06083285c90c8803e5a2621ac2b6e3b
    recent_invites_count = User.objects.filter(
        invited_by=owner,
        date_joined__gte=time_threshold,
    ).count()
<<<<<<< HEAD

    if recent_invites_count >= settings.MAX_INVITE_USES_COUNT:
=======
    
    if recent_invites_count >= int(settings.MAX_INVITE_USES_COUNT):
>>>>>>> fd172f14a06083285c90c8803e5a2621ac2b6e3b
        return False
    return True
