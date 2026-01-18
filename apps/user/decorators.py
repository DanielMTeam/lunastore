from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

# check developer account status
def developer_required(view_func=None, redirect_url='index'):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            is_developer = (
                request.user.is_authenticated and 
                (request.user.groups.filter(name='Разработчики').exists() or request.user.is_superuser)
            )
            
            if not is_developer:
                messages.error(request, "У вас нет статуса разработчика для просмотра этой страницы")
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    if view_func:
        return decorator(view_func)
    return decorator