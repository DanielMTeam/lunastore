from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from .forms import BroadcastNotificationForm
from django.contrib.auth import get_user_model
from django.contrib import admin
from .tasks import broadcast_notification_task

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

            user_ids = list(users.values_list('id', flat=True))
            if user_ids:
                broadcast_notification_task.enqueue(
                    user_ids=user_ids,
                    title=title,
                    content=content,
                    meta=meta_data,
                )
                if target_user_id:
                    messages.success(
                        request,
                        f"Уведомление для пользователя ID {target_user_id} передано в очередь фоновой доставки."
                    )
                else:
                    messages.success(
                        request,
                        f"Массовая рассылка передана в очередь фоновой доставки ({len(user_ids)} получателей)."
                    )
    else:
        form = BroadcastNotificationForm()

    context = {
        **admin.site.each_context(request),
        "title": "Рассылка уведомлений",
        "form": form,
    }

    return render(request, "admin/broadcast_notify.html", context)
