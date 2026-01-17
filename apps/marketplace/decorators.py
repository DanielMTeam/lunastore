from functools import wraps
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

# check, if user is a owner of something
def user_is_owner(model, url_param='pk', owner_field='user'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            obj = get_object_or_404(model,pk=kwargs.get(url_param))
            owner = getattr(obj,owner_field)
            if owner != request.user:
                raise PermissionDenied("Вы не являетесь администратором данного приложения.")
            return view_func(request,*args,**kwargs)
        return _wrapped_view
    return decorator