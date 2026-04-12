from functools import wraps
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

# check, if user is a owner of something
def user_is_owner(model, url_param='pk', owner_field='user'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            obj = get_object_or_404(model,pk=kwargs.get(url_param))
            owner = getattr(obj,owner_field)
            if owner != request.user:
                raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))
            return view_func(request,*args,**kwargs)
        return _wrapped_view
    return decorator
