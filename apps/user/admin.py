from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.db import models
from django.shortcuts import redirect
from django.utils.html import format_html
from unfold import admin as unfold_admin
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import action
from django.http import HttpResponseRedirect
from django.urls import reverse
from apps.core.tasks import send_notification

from lunastore.mixins import SafeDeleteAdmin

from .forms import AddToGroupForm, UserBanForm
from .models import (
    BlacklistedUsername,
    DevRequestsModel,
    InviteToken,
    User,
    UserActivityLog,
    UserBan,
)
from .tasks import CACHE_KEY


@admin.register(User)
class UserAdmin(BaseUserAdmin, unfold_admin.ModelAdmin):
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "username",
                    "email",
                    "description",
                    "password",
                    "avatar_path",
                    "avatar_id",
                    "badges",
                    "profile_splash",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                    "invited_by",
                ),
                "description": 'флаг is_staff является так называемым "пропуском" в админ-панель Django. флаг is_superuser дает все права без исключения. подумай дважды, прежде чем ставить эти флаги! (да блять, я серьезно)',
            },
        ),
        (
            "Дополнительная информация",
            {"fields": ("telegram", "discord", "openvk", "website")},
        ),
        (
            "Безопасность (2FA)",
            {"fields": ("totp_enabled", "totp_secret")},
        ),
    )
    list_display = ["pk", "username", "email", "invited_by"]
    search_fields = ["username", "email", "pk"]
    actions = ["disable_2fa"]
    actions_detail = ["login_as_user"]

    @action(description="Принудительно отключить 2FA", icon="lock_open", attrs={"class": "bg-warning-600 text-white"})
    def disable_2fa(self, request, queryset):
        count = queryset.update(totp_enabled=False, totp_secret=None)
        self.message_user(request, f"2FA успешно отключен для {count} пользователей.")

    @action(description="Войти от имени пользователя", icon="login", attrs={"class": "bg-primary-600 text-white"})
    def login_as_user(self, request, object_id):
        if not request.user.is_superuser:
            self.message_user(request, "Только суперпользователи могут входить от чужого имени.", messages.ERROR)
            return redirect(reverse("admin:user_user_change", args=[object_id]))

        user_to_impersonate = self.get_object(request, object_id)
        original_admin_id = request.user.id
        
        from django.contrib.auth import login
        login(request, user_to_impersonate, backend="django.contrib.auth.backends.ModelBackend")
        
        request.session["impersonated_by"] = original_admin_id
        
        host = request.get_host()
        if ":8088" in host:
            host = host.replace(":8088", ":9088")
        frontend_url = f"{request.scheme}://{host}/index.php"
        
        return redirect(frontend_url)

    def save_model(self, request, obj, form, change):
        if obj.password:
            if not obj.password.startswith(
                ("bcrypt", "pbkdf2_sha256", "pbkdf2_sha1", "argon2", "scrypt")
            ):
                obj.set_password(obj.password)

            super().save_model(request, obj, form, change)


@admin.register(UserBan)
class UserBanAdmin(SafeDeleteAdmin):
    form = UserBanForm
    list_display = (
        "get_username",
        "reason",
        "is_permanent_display",
        "expires_at",
        "ban_by_ip_display",
        "created_at",
    )
    list_filter = SafeDeleteAdmin.list_filter + [
        "created_at",
        "is_permanent",
        "ban_by_ip",
    ]
    search_fields = ["user__username", "reason", "ip"]
    actions = ["unban_selected_users", "remove_ip_ban_only"]

    @admin.display(description="Пользователь", ordering="user__username")
    def get_username(self, obj):
        return obj.user.username

    @admin.display(description="Бан по IP?", ordering="ip")
    def ban_by_ip_display(self, obj):
        return obj.ip

    @admin.display(description="Перманентный?", ordering="is_permanent")
    def is_permanent_display(self, obj):
        return obj.is_permanent

    @admin.action(description="Разблокировать пользователей")
    def unban_selected_users(self, request, queryset):
        users_unbanned_count = 0
        for ban_entry in queryset:
            user = ban_entry.user
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
            ban_entry.delete()
            users_unbanned_count += 1
        if users_unbanned_count > 0:
            self.message_user(
                request, f"Успешно разблокировано {users_unbanned_count} пользователей."
            )

    @admin.action(description="Снять блокировку по IP (но, оставить бан аккаунта)")
    def remove_ip_ban_only(self, request, queryset):
        updated_count = queryset.filter(ban_by_ip=True).update(ban_by_ip=False, ip=None)

        if updated_count > 0:
            from django.core.cache import cache

            cache.delete(CACHE_KEY)
            self.message_user(
                request, f"Успешно снята блокировка по IP для {updated_count} записей"
            )
        else:
            self.message_user(
                request,
                "Среди выбранных записей нет блокировок по IP",
                level=messages.WARNING,
            )


admin.site.unregister(Group)


class GroupAdmin(unfold_admin.ModelAdmin):
    form = AddToGroupForm
    filter_horizontal = ["permissions",]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "users" not in self.filter_horizontal:
            self.filter_horizontal = tuple(self.filter_horizontal) + ("users",)

        return form


admin.site.register(Group, GroupAdmin)
admin.site.register(UserActivityLog)


@admin.register(DevRequestsModel)
class DevRequestsAdmin(SafeDeleteAdmin):
    change_list_template = "admin/decline_forms/change_list_custom.html"
    change_form_template = "admin/decline_forms/change_form_custom.html"


    list_display = ("id", "user", "github", "mail")
    search_fields = ["github", "mail"]
    list_filter = SafeDeleteAdmin.list_filter + [
        "id",
    ]
    actions = ["approve_request", "reject_request"]
    actions_detail = ["approve_request", "reject_request"]
    readonly_fields = (
        "user_info_link",
        "user",
        "mail",
        "github",
        "about_you",
        "why_you_choose_us",
    )

    def user_info_link(self, obj):
        if not obj.user:
            return "No user associated"

        url_site = f"/profile.php?id={obj.user.id}"

        return format_html(
            """
            <div style="line-height: 1.5;">
                <a href="{}" target="_blank" style="font-weight: bold;">🔗 Профиль на сайте</a><br>
                <br>
                <span style="color: #666;">Email:</span> {}<br>
                <span style="color: #666;">Юзернейм:</span> {}<br>
                <span style="color: #666;">Дата регистрации:</span> {}
            </div>
            """,
            url_site,
            obj.user.email,
            obj.user.username,
            obj.user.date_joined.strftime("%d.%m.%Y %H:%M"),
        )

    user_info_link.short_description = ""

    @action(
        description="Одобрить заявку",
        icon="check_circle",
        attrs={"class": "bg-success-600 text-white"},
    )
    def approve_request(self, request, queryset=None, object_id=None, **kwargs):
        if queryset is None:
            queryset = self.get_queryset(request).filter(pk=object_id)
        group, created = Group.objects.get_or_create(name="Разработчики")

        success_count = 0
        for dev_request in queryset:
            user = dev_request.user
            if user:
                user.groups.add(group)
                success_count += 1
                send_notification.enqueue(
                    user_id=dev_request.user.id,
                    title_key="NOTIF_DEVSTATUS_ACCEPTED_TITLE",
                    content_key="NOTIF_DEVSTATUS_ACCEPTED_DESCRIPTION",
                    meta={"icon": "help.png"}
                )
                dev_request.delete()
        self.message_user(
            request,
            f"Успешно одобрено {success_count} заявок и добавлено в группу 'Разработчики'.",
            messages.SUCCESS,
        )
        opts = self.model._meta
        return redirect(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    @action(
        description="Отклонить заявку",
        icon="cancel",
        attrs={"class": "bg-error-600 text-white"},
    )
    def reject_request(self, request, queryset=None, object_id=None, **kwargs):
        if queryset is None:
            queryset = self.get_queryset(request).filter(pk=object_id)

        opts = self.model._meta
        changelist_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        reason = request.POST.get("reject_reason")

        if not reason:
            self.message_user(request, "Ошибка: Причина не была указана.", messages.ERROR)
            referer = request.META.get("HTTP_REFERER", changelist_url)
            return HttpResponseRedirect(referer)

        count = queryset.count()
        for dev_request in queryset:
            if dev_request.user:
                send_notification.enqueue(
                    user_id=dev_request.user.id,
                    title_key="NOTIF_DEVSTATUS_DECLINED_TITLE",
                    content_key="NOTIF_DEVSTATUS_DECLINED_DESCRIPTION",
                    context={"reason": reason},
                    meta={"icon": "help.png"}
                )

        queryset.delete()
        self.message_user(
            request, f"Отклонено и удалено заявок: {count}", messages.SUCCESS
        )
        opts = self.model._meta
        return redirect(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    fieldsets = (
        (
            "Основная информация по заявке",
            {
                "fields": ("user", "mail", "github", "about_you", "why_you_choose_us"),
                "description": "Информация, предоставленная пользователем в заявке на статус разработчика",
            },
        ),
        (
            "Информация по объекту User (пользователю)",
            {
                "fields": ("user_info_link",),
                "description": "Информация о пользователе, подавшем заявку",
            },
        ),
    )


@admin.register(BlacklistedUsername)
class BlacklistedUsernameAdmin(SafeDeleteAdmin):
    list_display = ("word", "is_regex")
    search_fields = ["word"]
    list_filter = SafeDeleteAdmin.list_filter + [
        "is_regex",
    ]


@admin.register(InviteToken)
class InviteTokenAdmin(unfold_admin.ModelAdmin):
    list_display = ("owner", "code", "created_at")
    list_filter = ("created_at",)
