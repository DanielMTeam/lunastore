from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.models import Group

from django.contrib.auth import login as dj_login, logout as dj_logout
from django.contrib.auth.forms import AuthenticationForm
from .models import UserBan
from .forms import user_registration
import json


def login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        form_data = {'username': data.get('username'), 'password': data.get('password')}
        form = AuthenticationForm(request, data=form_data)
        
        if form.is_valid():
            user = form.get_user()
            ban = UserBan.objects.filter(user=user).first()
            if ban:
                return JsonResponse({'success': False, 'errors': f'This account is banned. Reason: {ban.reason}'}, status=403)
            else:
                dj_login(request, user)
                return JsonResponse({'success': True, 'username': user.username})
        else:
            return JsonResponse({'success': False, 'errors': 'Password or username is not correct'}, status=400)
    return JsonResponse({'success': False, 'errors': 'Only POST method is allowed'}, status=405)

def logout(request):
    dj_logout(request)
    return redirect('/index.php')

def register(request):
    if not settings.REGISTRATION_IS_ENABLED:
        return render(request, 'register.html')

    if request.method == 'POST':
        form = user_registration(request.POST)
        if form.is_valid():
            user = form.save()
            user_group = Group.objects.get(name='Пользователи')
            user.groups.add(user_group) 
            dj_login(request, user)
            return redirect('home')
    else:
        form = user_registration()
    return render(request, 'register_on.html', { "form": form })
