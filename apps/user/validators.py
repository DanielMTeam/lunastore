import re
from datetime import timedelta

from constance import config
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import validate_email
import dns.resolver
import dns.exception
from disposable_email_domains import blocklist
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _


def validate_username_blacklist(value):
    from .models import BlacklistedUsername
    low_value = value.lower()
    blacklist = BlacklistedUsername.objects.all()

    for item in blacklist:
        if item.is_regex:
            if re.search(item.word, low_value):
                raise ValidationError(f"Nickname containce ban-pattern: {item.word}")
        elif item.word.lower() in low_value:
            raise ValidationError("Nickname containcs ban-word(-s)")


def validate_invite_limit(owner):
    from .models import User

    time_threshold = timezone.now() - timedelta(
        days=int(config.MAX_INVITE_DAYS_LIMIT)
    )

    recent_invites_count = User.objects.filter(
        invited_by=owner,
        date_joined__gte=time_threshold,
    ).count()

    if recent_invites_count >= int(config.MAX_INVITE_USES_COUNT):
        return False
    return True


def validate_email_mx(value):
    # base check of syntax
    try:
        validate_email(value)
    except ValidationError:
        raise ValidationError(_('ERROR_EMAIL_INVALID_FORMAT'))

    # split email into local part and domain
    try:
        local_part, domain = value.rsplit('@', 1)
    except ValueError:
        raise ValidationError(_('ERROR_EMAIL_INVALID_FORMAT'))

    # block aliases
    if '+' in local_part:
        raise ValidationError(_('ERROR_EMAIL_NO_ALIASES'))

    domain = domain.lower()

    if domain in blocklist:
        raise ValidationError(_('ERROR_EMAIL_DISPOSABLE_DOMAIN'))

    # check MX records (using cache)
    cache_key = f'mx_record_{domain}'
    has_mx = cache.get(cache_key)

    if has_mx is None:
        try:
            # set hard timeouts
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2.0
            resolver.lifetime = 2.0
            resolver.resolve(domain, 'MX')
            has_mx = True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
            has_mx = False
        except Exception:
            # if DNS server is down, skip to avoid breaking registration
            has_mx = True

        # cache: valid domains for 24 hours, invalid for 1 hour
        cache_timeout = 86400 if has_mx else 3600
        cache.set(cache_key, has_mx, cache_timeout)
    if not has_mx:
        raise ValidationError(
            _('ERROR_EMAIL_DOMAIN_NO_MX %(domain)s'),
            params={'domain': domain},
        )
