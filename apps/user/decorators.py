from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render


# check developer account status
def developer_required(view_func=None, redirect_url='index'):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            is_developer = (
                request.user.is_authenticated and (
                    request.user.groups.filter(
                        name='Разработчики').exists() or request.user.is_superuser))

            if not is_developer:
                messages.error(request, _("ERROR_YOU_DONT_HAVE_DEVSTATUS"))
                return redirect(redirect_url)

            return view_func(request, *args, **kwargs)

        return wrapped_view
    if view_func:
        return decorator(view_func)
    return decorator


def is_outdated_browser(request):
    if hasattr(request, 'user_agent'):
        browser = request.user_agent.browser
        family = browser.family
        version = browser.version[0] if browser.version else 0

        return (
            # block only IE 6 and 7 (six seveeeeeeen)
            (family == 'IE' and version in [6, 7]) or
            family == 'Opera Mini' or
            (family == 'Safari' and version < 11) or
            (family in ['Chrome', 'Firefox'] and version < 60)
        )
    return False


def is_modern_browser(request):
    return not is_outdated_browser(request)


def require_modern_browser(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if is_outdated_browser(request):
            return render(request, "badbrowser.html", status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped_view
