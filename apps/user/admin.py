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
    NoSpamEvent,
    NoSpamRule,
    User,
    UserActivityLog,
    UserBan,
)
from .tasks import CACHE_KEY


@admin.register(User)
class UserAdmin(BaseUserAdmin, unfold_admin.ModelAdmin):
    fieldsets = (("Основная информация",
                  {"fields": ("username",
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
                 ("Дополнительная информация",
                  {"fields": ("telegram",
                              "discord",
                              "openvk",
                              "website")},
                  ),
                 ("Безопасность (2FA)",
                  {"fields": ("totp_enabled",
                              "totp_secret")},
                  ),
                 )
    list_display = ["pk", "display_username", "email", "invited_by"]
    search_fields = ["username", "email", "pk"]
    actions = ["disable_2fa"]
    actions_detail = ["login_as_user"]

    @admin.display(description="Юзернейм", ordering="username")
    def display_username(self, obj):
        return obj.username

    @action(description="Принудительно отключить 2FA", icon="lock_open",
            attrs={"class": "bg-warning-600 text-white"})
    def disable_2fa(self, request, queryset):
        count = queryset.update(totp_enabled=False, totp_secret=None)
        self.message_user(
            request,
            f"2FA успешно отключен для {count} пользователей.")

    @action(description="Войти от имени пользователя", icon="login",
            attrs={"class": "bg-primary-600 text-white"})
    def login_as_user(self, request, object_id):
        from constance import config
        is_moderator = request.user.groups.filter(name='Модераторы').exists()

        if not request.user.is_superuser:
            if not (is_moderator and config.ALLOW_MODERATOR_LOGIN_AS_USER):
                self.message_user(
                    request,
                    "Только суперпользователи (или модераторы, если разрешено) могут входить от чужого имени.",
                    messages.ERROR)
                return redirect(
                    reverse(
                        "admin:user_user_change",
                        args=[object_id]))

        user_to_impersonate = self.get_object(request, object_id)
        original_admin_id = request.user.id

        from django.contrib.auth import login
        login(
            request,
            user_to_impersonate,
            backend="django.contrib.auth.backends.ModelBackend")

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
                request, f"Успешно разблокировано {users_unbanned_count} пользователей.")

    @admin.action(description="Снять блокировку по IP (но, оставить бан аккаунта)")
    def remove_ip_ban_only(self, request, queryset):
        updated_count = queryset.filter(
            ban_by_ip=True).update(
            ban_by_ip=False, ip=None)

        if updated_count > 0:
            from django.core.cache import cache

            cache.delete(CACHE_KEY)
            self.message_user(
                request, f"Успешно снята блокировка по IP для {updated_count} записей")
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
    def approve_request(
            self,
            request,
            queryset=None,
            object_id=None,
            **kwargs):
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
        changelist_url = reverse(
            f"admin:{
                opts.app_label}_{
                opts.model_name}_changelist")
        reason = request.POST.get("reject_reason")

        if not reason:
            self.message_user(
                request,
                "Ошибка: Причина не была указана.",
                messages.ERROR)
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

    fieldsets = (("Основная информация по заявке",
                  {"fields": ("user",
                              "mail",
                              "github",
                              "about_you",
                              "why_you_choose_us"),
                   "description": "Информация, предоставленная пользователем в заявке на статус разработчика",
                   },
                  ),
                 ("Информация по объекту User (пользователю)",
                  {"fields": ("user_info_link",
                              ),
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


@admin.register(NoSpamRule)
class NoSpamRuleAdmin(unfold_admin.ModelAdmin):
    list_display = (
        "name",
        "is_enabled",
        "priority",
        "entrypoints",
        "action",
        "match_type",
        "updated_at",
    )
    search_fields = ("name", "pattern", "reason_template", "entrypoints")
    list_filter = ("is_enabled", "action", "match_type", "is_permanent", "ban_by_ip")
    actions = ("enable_rules", "disable_rules")
    actions_detail = ("enable_rule_detail", "disable_rule_detail")
    list_filter_submit = True
    fieldsets = (
        (
            "Как работать",
            {
                "fields": (),
                "description": (
                    "<p><strong>Быстрый старт:</strong></p>"
                    "<ol>"
                    "<li>Включите <code>NOSPAM_ENABLED</code> в "
                    "<em>Настройки сайта → NoSpam и anti-raider</em>.</li>"
                    "<li>Создайте правило с действием <strong>Только лог</strong> "
                    "и проверьте срабатывания в разделе "
                    "<em>noSpam события</em>.</li>"
                    "<li>Если правило ловит нужных — смените действие на "
                    "<strong>Бан</strong> или <strong>Удаление</strong>.</li>"
                    "</ol>"
                    "<p><strong>Типы фильтров:</strong></p>"
                    "<ul>"
                    "<li><strong>Домен email</strong> — паттерн: <code>tempmail.com</code></li>"
                    "<li><strong>Email / Username / User-Agent / Invite regex</strong> — "
                    "обычное regex, например <code>^bot</code> или <code>.*@mail\\.ru$</code></li>"
                    "<li><strong>IP CIDR</strong> — подсеть, например <code>10.0.0.0/8</code></li>"
                    "<li><strong>Код страны</strong> — ISO-код: <code>RU</code>, <code>US</code></li>"
                    "<li><strong>Диапазон ID</strong> — формат <code>мин:макс</code>, "
                    "например <code>100:500</code> (можно одно значение: <code>42</code>)</li>"
                    "<li><strong>Сигнал скорости</strong> — в payload: "
                    "<code>{\"max_hits\": 5, \"window_seconds\": 60}</code></li>"
                    "</ul>"
                    "<p><strong>Точки входа</strong> (через запятую): "
                    "<code>register</code>, <code>login</code>, <code>jwt_token</code>, "
                    "<code>profile_email</code>, <code>profile_username</code>, "
                    "<code>dev_status</code>. Если поле пустое — правило работает везде.</p>"
                    "<p><strong>Пример:</strong> блок домена на регистрации — "
                    "тип <em>Домен email</em>, паттерн <code>guerrillamail.com</code>, "
                    "точки входа <code>register</code>, действие <em>Бан</em>.</p>"
                ),
            },
        ),
        (
            "Основное",
            {
                "fields": (
                    "name",
                    "is_enabled",
                    "priority",
                    "entrypoints",
                    "action",
                    "reason_template",
                ),
            },
        ),
        (
            "Условие срабатывания",
            {
                "fields": (
                    "match_type",
                    "pattern",
                    "payload",
                ),
                "description": (
                    "Поле <strong>Паттерн</strong> зависит от типа фильтра. "
                    "Для <em>Сигнала скорости</em> используйте "
                    "<strong>Доп. настройки</strong> (JSON), а не паттерн."
                ),
            },
        ),
        (
            "Параметры бана",
            {
                "fields": (
                    "ban_by_ip",
                    "is_permanent",
                    "ban_duration_minutes",
                ),
                "description": (
                    "Используется только при действии <strong>Бан</strong>. "
                    "Если перманентный бан выключен — срок берётся из "
                    "<em>Длительность бана (мин)</em>."
                ),
            },
        ),
    )

    @admin.action(description="Включить выбранные правила")
    def enable_rules(self, request, queryset):
        count = queryset.update(is_enabled=True)
        self.message_user(request, f"Включено правил: {count}", level=messages.SUCCESS)

    @admin.action(description="Выключить выбранные правила")
    def disable_rules(self, request, queryset):
        count = queryset.update(is_enabled=False)
        self.message_user(request, f"Выключено правил: {count}", level=messages.SUCCESS)

    @action(
        description="Включить правило",
        icon="toggle_on",
        attrs={"class": "bg-success-600 text-white"},
    )
    def enable_rule_detail(self, request, object_id):
        rule = self.get_object(request, object_id)
        if rule is None:
            self.message_user(request, "Правило не найдено.", level=messages.ERROR)
            return redirect(reverse("admin:user_nospamrule_changelist"))
        rule.is_enabled = True
        rule.save(update_fields=["is_enabled"])
        self.message_user(request, f"Правило «{rule.name}» включено.", level=messages.SUCCESS)
        return redirect(reverse("admin:user_nospamrule_change", args=[object_id]))

    @action(
        description="Выключить правило",
        icon="toggle_off",
        attrs={"class": "bg-warning-600 text-white"},
    )
    def disable_rule_detail(self, request, object_id):
        rule = self.get_object(request, object_id)
        if rule is None:
            self.message_user(request, "Правило не найдено.", level=messages.ERROR)
            return redirect(reverse("admin:user_nospamrule_changelist"))
        rule.is_enabled = False
        rule.save(update_fields=["is_enabled"])
        self.message_user(request, f"Правило «{rule.name}» выключено.", level=messages.SUCCESS)
        return redirect(reverse("admin:user_nospamrule_change", args=[object_id]))


@admin.register(NoSpamEvent)
class NoSpamEventAdmin(unfold_admin.ModelAdmin):
    list_display = ("created_at", "entrypoint", "action", "ip", "user", "rule", "reason")
    search_fields = ("entrypoint", "reason", "ip", "matched_value")
    list_filter = ("entrypoint", "action", "created_at")
    fieldsets = (
        (
            "О событии",
            {
                "fields": (
                    "created_at",
                    "entrypoint",
                    "action",
                    "reason",
                    "rule",
                    "user",
                    "ip",
                    "matched_value",
                    "context",
                ),
                "description": (
                    "Журнал срабатываний noSpam. Используйте его для проверки правил "
                    "в режиме <strong>Только лог</strong> перед включением бана или удаления."
                ),
            },
        ),
    )
    readonly_fields = (
        "created_at",
        "entrypoint",
        "action",
        "ip",
        "user",
        "rule",
        "reason",
        "matched_value",
        "context",
    )

    def has_add_permission(self, request):
        return False
