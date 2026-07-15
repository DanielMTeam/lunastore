from django.core.cache import cache
from .models import BlacklistedUsername

CACHE_KEY_BLACKLIST = "blacklisted_usernames"


def get_cached_blacklist():
    """
    returns the cached list of BlacklistedUsername objects
    if the cache is empty, it queries the database and caches the result for 24 hours
    """
    blacklist = cache.get(CACHE_KEY_BLACKLIST)
    if blacklist is None:
        blacklist = list(BlacklistedUsername.objects.all())
        cache.set(CACHE_KEY_BLACKLIST, blacklist, 86400)  # cache for 24 hours
    return blacklist
