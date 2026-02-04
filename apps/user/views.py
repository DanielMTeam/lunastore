from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login as dj_login, logout as dj_logout, update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .models import UserBan, UserActivityLog, User, DevRequestsModel, BlacklistedUsername
from apps.marketplace.models import Application
from .forms import UserRegistrationForm, AvatarUpdateForm, ProfileUpdateForm, PasswordChangeForm, DevStatusForm, PasswordConfirmationForm
import json
from .middleware import get_client_ip, BlockBannedIP
import re
import django,sys,platform
from django.utils.translation import gettext_lazy as _


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
        ban = UserBan.objects.filter(user=user).first()
        if ban:
            return JsonResponse({'success': False, 'errors': f'Your account is banned. Reason: {ban.reason}'}, status=403)
        else:
            user.backend = 'django.contrib.auth.backends.ModelBackend'
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
    print(request.META.get('REMOTE_ADDR'))
    if not settings.REGISTRATION_IS_ENABLED:
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, 'register.html')

    if request.method == 'POST':
        if request.user.is_authenticated:
            return redirect('home')
        raw_username = request.POST.get('username', '').lower().strip()
        blacklist = BlacklistedUsername.objects.all()
        is_blocked = False
        
        for item in blacklist:
            if item.is_regex:
                if re.search(item.word, raw_username):
                    is_blocked = True
                    break
            else:
                if item.word.lower() in raw_username:
                    is_blocked = True
                    break
        if is_blocked:
            return redirect('502_error')
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
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            dj_login(request, user)
            return redirect('home')
    else:
        if request.user.is_authenticated:
            return redirect('home')
        form = UserRegistrationForm(request=request)
    return render(request, 'register_on.html', {"form": form})


def profile(request):
    id = request.GET.get('id')
    if id:
        obj = get_object_or_404(User, id=id)
        return render(request, 'profile.html', context={'obj': obj})
    else:
        if not request.user.is_authenticated:
            raise Http404("No ID provided and you (maybe; or you just have a problem with your cookie) is anonymous")
        obj = get_object_or_404(User, id=request.user.id)
        return render(request, 'profile.html', context={'obj': obj})


@login_required
def profile_settings(request):
    user = request.user
    forms = {
        'profile_form': ProfileUpdateForm(instance=user),
        'password_form': PasswordChangeForm(user=user),
        'avatar_form': AvatarUpdateForm(instance=user),
        'del_acc_form': PasswordConfirmationForm(user=user),
    }
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'profile':
            forms['profile_form'] = ProfileUpdateForm(request.POST, instance=user)
            if forms['profile_form'].is_valid():
                forms['profile_form'].save()
                messages.success(request, _("INFO_PROFILE_IS_UPDATED"))
                return redirect('settings')
        elif form_type == 'password':
            forms['password_form'] = PasswordChangeForm(user=user, data=request.POST)
            if forms['password_form'].is_valid():
                user.set_password(forms['password_form'].cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, _("INFO_PASSWORD_WAS_CHANGED"))
                return redirect('settings')
        elif form_type == 'avatar':
            forms['avatar_form'] = AvatarUpdateForm(request.POST, request.FILES, instance=user)
            if forms['avatar_form'].is_valid():
                forms['avatar_form'].save()
                messages.success(request, _("INFO_AVATAR_WAS_CHANGED"))
                return redirect('settings')
        elif form_type == 'init_delete':
            request.session['can_view_delete_page'] = True
            return redirect('delete_account')
    return render(request, 'settings.html', forms)


@login_required
def dev_status(request):
    user = request.user
    is_developer = request.user.groups.filter(name='Разработчики').exists()
    has_pending_request = DevRequestsModel.objects.filter(user=request.user).exists()
    # initialize the form
    if request.method == 'POST':
        form = DevStatusForm(request.POST, instance=user)
        if form.is_valid():
            # save model data
            form.save()
            # get cleaned data
            cd = form.cleaned_data

            # create DevRequestsModel entry
            DevRequestsModel.objects.create(
                user=user,
                github=cd.get('github'),
                mail=cd.get('mail'),
                about_you=cd.get('about_you'),
                why_you_choose_us=cd.get('why_you_choose_us')
            )

            messages.success(request, _("INFO_APP_CREATE_REQUEST_WAS_SENT"))
            return redirect('home')
    else:
        form = DevStatusForm(instance=user)

    # render the template with the form
    return render(request, 'dev_add.html', {'dev_request_form': form, 'is_developer': is_developer, 'has_pending_request': has_pending_request, "registration_enabled_status": settings.DEVELOPER_REGISTRATION_IS_ENABLED})

def critical_error(request):
    return render(request, '502.html')

@login_required 
def delete_account(request):
    if not request.session.get('can_view_delete_page'):
        messages.warning(request, _("ERROR_ACCESS_DENIED_PROFILE"))
        return redirect('settings')
    if request.method == 'POST':
        form = PasswordConfirmationForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            user.delete()
            messages.success(request, _('INFO_ACCOUNT_WAS_DELETED'))
            return redirect('home')
    else:
        form = PasswordConfirmationForm(request.user)
    apps_loaded_count = Application.objects.filter(user=request.user).count()
    print(apps_loaded_count)
    return render(request, 'del_acc.html', {'apps_count':apps_loaded_count,'form':form})

def debug_info(request):
    if settings.DEBUG:
        method = request.method 
        user_ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT')
        
        django_version = django.get_version()
        python_version = sys.version
        os_info = platform.platform()
        return render(request, 'debug_info.html', {'method':method,'user_ip':user_ip,'user_agent':user_agent,'django_version':django_version,'python_version':python_version,'os_info':os_info})
    return redirect('home')