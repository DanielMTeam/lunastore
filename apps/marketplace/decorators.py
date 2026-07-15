from functools import wraps
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

from apps.marketplace.models import Application

# check, if user is a owner of something


def user_is_owner(model, url_param='pk', owner_field='user'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            obj = get_object_or_404(model, pk=kwargs.get(url_param))
            owner = getattr(obj, owner_field)

            # my pussy tastes like pepsi cola
            # my eyes are wide like cherry pies
            # i gots a taste for men who are older
            # it's always been so it's no surprise

            if owner != request.user:
                raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def guard_private_app(view_func=None):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            app_instance = get_object_or_404(
                Application, pk=request.GET.get("id"))

            if not app_instance.is_private:
                return view_func(request, *args, **kwargs)

            owner = app_instance.user

            if owner != request.user:
                raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    if view_func:
        return decorator(view_func)

    return decorator
