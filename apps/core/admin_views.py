import jwt
import requests
import time
from django.conf import settings
from django.shortcuts import render
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from .forms import BroadcastNotificationForm
from django.contrib.auth import get_user_model
from django.contrib import admin

User = get_user_model()


@user_passes_test(lambda u: u.is_active and u.is_superuser)
def admin_broadcast_notification(request):
    if request.method == 'POST':
        form = BroadcastNotificationForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            content = form.cleaned_data['content']
            level = form.cleaned_data['level']
            target_user_id = form.cleaned_data.get('user_id')

            meta_data = {
                "type": level,
                "icon": "system.png"
            }

            if target_user_id:
                # send to one user
                try:
                    target_user = User.objects.get(id=target_user_id)
                    users = [target_user]
                except User.DoesNotExist:
                    messages.error(
                        request, f"Пользователь с ID {target_user_id} не найден.")
                    users = []
            else:
                # send to all active users
                users = User.objects.filter(is_active=True)

            success_count = 0
            api_url = getattr(
                settings,
                'LUNASPIRE_URL',
                'http://192.168.48.128:8080')

            # send notifications
            for u in users:
                payload = {
                    "type": "notify-send",
                    "title": title,
                    "content": content,
                    "user_id": int(u.id),
                    "meta": meta_data,
                    "exp": int(time.time()) + 600
                }
                token = jwt.encode(
                    payload,
                    settings.LUNASPIRE_SECRET_KEY,
                    algorithm="HS256")

                try:
                    resp = requests.put(
                        f"{api_url}/notifications/send?token={token}",
                        timeout=2
                    )
                    print(token)
                    print(resp.text, resp.status_code)
                    if resp.status_code == 200:
                        success_count += 1
                except Exception as e:
                    messages.error(
                        request,
                        f"Ошибка отправки уведомления для ID {
                            u.id}: {e}")

            if users:
                if target_user_id:
                    messages.success(
                        request, f"Уведомление успешно отправлено пользователю ID {target_user_id}.")
                else:
                    messages.success(
                        request, f"Массовая рассылка завершена. Доставлено: {success_count} шт.")
    else:
        form = BroadcastNotificationForm()

    context = {
        **admin.site.each_context(request),
        "title": "Рассылка уведомлений",
        "form": form,
    }

    return render(request, "admin/broadcast_notify.html", context)
