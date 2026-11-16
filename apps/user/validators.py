import logging
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

ENGLISH_USERNAME_REGEX = r"^[a-zA-Z0-9_.-]+$"
logger = logging.getLogger(__name__)


def validate_english_username(value):
    if not value or not isinstance(value, str):
        raise ValidationError(_("ERROR_USERNAME_EMPTY"))

    if not re.match(ENGLISH_USERNAME_REGEX, value):
        raise ValidationError(_("ERROR_USERNAME_INVALID_CHARS"))

    if not re.search(r"[a-zA-Z]", value):
        raise ValidationError(_("ERROR_USERNAME_NO_LETTERS"))

    if value.startswith(".") or value.endswith(".") or ".." in value:
        raise ValidationError(_("ERROR_USERNAME_INVALID_DOTS"))


def validate_username_blacklist(value):
    from .utils import get_cached_blacklist
    low_value = value.lower()
    blacklist = get_cached_blacklist()

    for item in blacklist:
        if item.is_regex:
            if re.search(item.word, low_value):
                raise ValidationError(
                    f"Nickname containce ban-pattern: {item.word}")
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
    # Previous entries also cached DNS outages as permanent validation failures.
    cache_key = f'mx_record_v2_{domain}'
    has_mx = cache.get(cache_key)

    if has_mx is None:
        try:
            # set hard timeouts
            resolver = dns.resolver.Resolver()
            resolver.timeout = 2.0
            resolver.lifetime = 2.0
            resolver.resolve(domain, 'MX')
            has_mx = True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            has_mx = False
        except (dns.exception.DNSException, OSError) as exc:
            # A resolver outage says nothing about whether the domain accepts mail.
            # Keep syntax/disposable checks, but retry DNS on the next validation.
            logger.warning("Email MX lookup unavailable for %s: %s", domain, type(exc).__name__)
            return

        # cache: valid domains for 24 hours, invalid for 1 hour
        cache_timeout = 86400 if has_mx else 3600
        cache.set(cache_key, has_mx, cache_timeout)
    if not has_mx:
        raise ValidationError(
            _('ERROR_EMAIL_DOMAIN_NO_MX %(domain)s'),
            params={'domain': domain},
        )
