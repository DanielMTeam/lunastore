import importlib.metadata
import platform
import shutil
import sys

import django
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils import timezone, translation


# Create your views here.
def debug_info(request):
    if settings.DEBUG:
        method = request.method
        user_agent = request.META.get("HTTP_USER_AGENT")
        django_version = django.get_version()
        python_version = sys.version
        os_info = platform.platform()
        lunastore_version = getattr(settings, "VERSION", "unknown")

        # ip and network
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        user_ip = (
            x_forwarded_for.split(",")[0].strip()
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )

        # disk usage
        try:
            total, used, free = shutil.disk_usage(settings.BASE_DIR)
            # bytes to gigabytes
            free_gb = f"{free // (2**30)} GB"
            total_gb = f"{total // (2**30)} GB"
            disk_info = f"Free {free_gb} from {total_gb}"
        except Exception:
            disk_info = "not available"

        # versions of packages
        important_packages = [
            "Pillow",
            "psycopg",
            "Django",
            "gunicorn",
            "djangorestframework",
            "drf-spectacular",
            "mozilla-django-oidc",
            "django-unfold",
            "django-simple-captcha",
            "django-cleanup",
            "django-safedelete",
        ]
        installed_packages = {}
        for pkg in important_packages:
            try:
                installed_packages[pkg] = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                installed_packages[pkg] = "Not installed"

        # cache
        try:
            cache.set("debug_test_key", "ok", timeout=5)
            cache_status = (
                "all is ok"
                if cache.get("debug_test_key") == "ok"
                else "error reading/writing"
            )
        except Exception as e:
            cache_status = f"unavailable ({e})"

        # time and timezone
        server_time = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        time_zone = settings.TIME_ZONE

        return render(
            request,
            "debug_info.html",
            {
                "method": method,
                "user_ip": user_ip,
                "user_agent": user_agent,
                "django_version": django_version,
                "python_version": python_version,
                "os_info": os_info,
                "lunastore_version": lunastore_version,
                "disk_info": disk_info,
                "installed_packages": installed_packages,
                "cache_status": cache_status,
                "server_time": server_time,
                "time_zone": time_zone,
            },
        )
    return redirect("home")


def force_language_change(request, lang_code):
    next_url = request.GET.get("next", request.META.get("HTTP_REFERER", "/"))
    response = HttpResponseRedirect(next_url)

    lang_code = lang_code.lower()

    if lang_code and translation.check_for_language(lang_code):
        translation.activate(lang_code)
        is_secure = request.is_secure()
        samesite = "Lax" if not is_secure else "None"

        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            lang_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=is_secure,
            httponly=False,
            samesite=samesite,
        )

    return response
