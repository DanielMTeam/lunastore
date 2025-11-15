from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.models import Group

from django.contrib.auth import login as dj_login, logout as dj_logout
from django.contrib.auth.forms import AuthenticationForm
from .models import UserBanForm, UserActivityLog
from .forms import UserRegistrationForm
import json
from .middleware import get_client_ip, BlockBannedIP


def login(request):
    ip = get_client_ip(request)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'errors': 'Only POST method is allowed'}, status=405)
    
    if ip in BlockBannedIP.get_banned_set():
        return JsonResponse({'success': False, 'errors': 'Your IP address is banned.'}, status=403)
    if request.user.is_authenticated:
        return redirect('home')
    data = json.loads(request.body)
    form_data = {'username': data.get('username'), 'password': data.get('password')}
    form = AuthenticationForm(request, data=form_data)
    
    if form.is_valid():
        user = form.get_user()
        ban = UserBanForm.objects.filter(user=user).first()
        if ban:
            return JsonResponse({'success': False, 'errors': f'Your account is banned. Reason: {ban.reason}'}, status=403)
        else:
            dj_login(request, user)
            UserActivityLog.objects.create(
                user=user,
                ip=get_client_ip(request),
                action='login_save_ip'
            )
            return JsonResponse({'success': True, 'username': user.username})
    else:
        return JsonResponse({'success': False, 'errors': 'Password or username is not correct'}, status=400)

def logout(request):
    dj_logout(request)
    return redirect('/index.php')

def register(request):
    if not settings.REGISTRATION_IS_ENABLED:
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, 'register.html')

    if request.method == 'POST':
        if request.user.is_authenticated:
            return redirect('home')
        form = UserRegistrationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            user.save()
            user_group = Group.objects.get(name='Пользователи')
            user.groups.add(user_group)
            UserActivityLog.objects.create(
                    user=user,
                    ip=get_client_ip(request),
                    action='register_save_ip'
                )
            dj_login(request, user)
            return redirect('home')
    else:
        if request.user.is_authenticated:
            return redirect('home')
        form = UserRegistrationForm(request=request)    
    return render(request, 'register_on.html', {"form": form})
