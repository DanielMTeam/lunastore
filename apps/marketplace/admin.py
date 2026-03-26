from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold import admin as unfold_admin
from unfold.decorators import action

from lunastore.mixins import SafeDeleteAdmin

from .forms import ApplicationAdminForm
from .models import *


class DistributionInline(admin.TabularInline):
    model = Distribution
    fields = ("version", "url", "changelog", "published")
    readonly_fields = ("published",)
    extra = 0


@admin.register(Distribution)
class DistributionAdmin(SafeDeleteAdmin):
    list_display = ("app", "version", "published", "download_preview")
    list_filter = SafeDeleteAdmin.list_filter + ["app"]
    readonly_fields = ("published", "download_preview")
    ordering = ["-published"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "app",
                    "version",
                    "cdn_file_id",
                    "url",
                    "changelog",
                    "published",
                )
            },
        ),
    )

    @admin.display(description="Ссылка")
    def download_preview(self, obj):
        if obj.cdn_file_id:
            return format_html(
                '<a href="/get_dist_file/{}" target="_blank">файл</a>', obj.cdn_file_id
            )
        if obj.url:
            return format_html('<a href="{url}" target="_blank">{url}</a>', url=obj.url)
        return "-"


@admin.register(Category)
class CategoryAdmin(SafeDeleteAdmin):
    pass


@admin.register(Application)
class ApplicationAdmin(SafeDeleteAdmin):
    form = ApplicationAdminForm
    inlines = (DistributionInline,)
    readonly_fields = ("display_screenshots", "user")

    class Meta:
        model = Application

    # exclude = ["user"]

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "title",
                    "category",
                    "description",
                    "slogan",
                    "requirements",
                    "icon_file",
                    "cdn_icon_path",
                    "icon_path",
                    "developer_site",
                    "price",
                    "is_demo",
                    "is_under_dmca",
                )
            },
        ),
        (
            "Управление скриншотами",
            {
                "fields": (
                    "screenshots_files",
                    "cdn_screenshots_data",
                    "screenshots",
                    "display_screenshots",
                ),
            },
        ),
    )

    class Media:
        js = ("js/marketplace_cdn.js",)

    def render_change_form(self, request, context, *args, **kwargs):
        context.update(
            {
                "cdn_config": {
                    "uploadUrl": f"{settings.LUNASPIRE_URL}/cdn/upload",
                    "tokenUrl": f"{settings.API_URL}/method/user/getPubUploadToken",
                },
                "luna_i18n": {
                    "uploading": "Загрузка в LunaSpire...",
                    "error": "Ошибка: ",
                    "retry": "Повторить",
                    "tokenError": "Ошибка токена",
                    "fileError": "Ошибка файла: ",
                },
            }
        )
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.user_id:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def display_screenshots(self, obj):
        html = ""
        if obj.screenshots:
            for url in obj.screenshot_urls:
                html += f'<img src="{url}" height="90" style="margin-right: 10px; border-radius: 4px; border: 1px solid #ccc; object-fit: cover;" />'

        return mark_safe(html or "Нет скриншотов")

    display_screenshots.short_description = "Предпросмотр"

    list_display = ["title", "category", "is_demo", "is_under_dmca", "price"]
    list_editable = ["is_demo", "is_under_dmca"]
    list_filter = SafeDeleteAdmin.list_filter + ["is_demo", "is_under_dmca"]
    search_fields = ["title"]


@admin.register(AppCreateRequests)
class AppCreateRequestsAdmin(SafeDeleteAdmin):
    list_display = ("id", "title", "user", "status")
    search_fields = ["title", "id"]
    list_filter = SafeDeleteAdmin.list_filter + [
        "id",
        "status",
    ]
    actions = ["approve_request", "reject_request"]
    actions_detail = ["approve_request", "reject_request"]
    readonly_fields = (
        "user_info_link",
        "user",
        "status",
        "category",
        "title",
        "description",
        "slogan",
        "icon_preview",
        "price",
        "screenshots",
        "developer_site",
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

    def icon_preview(self, obj):
        if obj.icon_path:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="50" height="50" style="object-fit: cover; border-radius: 4px; border: 1px solid #ccc;" /></a>',
                obj.icon_url,
            )
        return "Нет иконки"

    user_info_link.short_description = ""

    @action(
        description="Одобрить заявку", icon="check_circle", url_path="approve-request"
    )
    def approve_request(self, request, object_id):
        req = self.get_object(request, object_id)

        if req.status == "approved":
            self.message_user(request, "Эта заявка уже одобрена", messages.WARNING)
            return redirect(
                reverse("admin:marketplace_appcreaterequests_change", args=[object_id])
            )

        Application.objects.create(
            user=req.user,
            category=req.category,
            title=req.title,
            description=req.description,
            slogan=req.slogan,
            price=req.price,
            icon_id=req.icon_id,
            icon_path=req.icon_path,
            screenshots=req.screenshots,
            developer_site=req.developer_site,
        )

        req.status = "approved"
        req.save()
        req.delete()
        self.message_user(request, "Приложение(-ия) успешно создано!", messages.SUCCESS)
        return redirect(
            reverse("admin:marketplace_appcreaterequests_change", args=[object_id])
        )

    @action(
        description="Отклонить заявку",
        icon="cancel",
        attrs={"class": "bg-error-600 text-white"},
    )
    def reject_request(self, request, object_id):
        req = self.get_object(request, object_id)
        req.status = "rejected"
        req.save()
        req.delete()
        self.message_user(request, "Заявка отклонена", messages.INFO)
        return redirect(
            reverse("admin:marketplace_appcreaterequests_change", args=[object_id])
        )

    fieldsets = (
        (
            "Основная информация по заявке",
            {
                "fields": (
                    "user",
                    "category",
                    "title",
                    "slogan",
                    "description",
                    "price",
                    "icon_path",
                    "screenshots",
                    "developer_site",
                ),
                "description": "Информация, предоставленная пользователем в заявке на создание приложения",
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


@admin.register(AppEditRequests)
class AppEditRequestsAdmin(SafeDeleteAdmin):
    list_display = ("id", "title", "user", "status")
    search_fields = ["title", "id"]
    list_filter = SafeDeleteAdmin.list_filter + [
        "id",
        "status",
    ]
    actions_detail = ["approve_request", "reject_request"]
    readonly_fields = (
        "user_info_link",
        "user",
        "status",
        "category",
        "title",
        "description",
        "requirements",
        "slogan",
        "icon_preview",
        "price",
        "screenshots",
        "developer_site",
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

    def icon_preview(self, obj):
        icon_url = obj.icon_url
        if not obj.icon_path and obj.target_application:
            icon_url = obj.target_application.icon_url

        return format_html(
            '<a href="{0}" target="_blank"><img src="{0}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" /></a>',
            icon_url,
        )

    user_info_link.short_description = ""

    @action(
        description="Одобрить заявку",
        icon="check_circle",
        attrs={"class": "bg-success-600 text-white"},
    )
    def approve_request(self, request, object_id):
        req = self.get_object(request, object_id)

        if req.status == "approved":
            self.message_user(request, "Заявка уже была одобрена", messages.WARNING)
            return redirect(
                reverse("admin:marketplace_appeditrequests_change", args=[object_id])
            )

        app = req.target_application
        if not app:
            self.message_user(
                request,
                "Ошибка: Целевое приложение не найдено (возможно, удалено)",
                messages.ERROR,
            )
            return redirect(
                reverse("admin:marketplace_appeditrequests_change", args=[object_id])
            )

        app.category = req.category
        app.title = req.title
        app.description = req.description
        app.slogan = req.slogan
        app.price = req.price
        app.developer_site = req.developer_site
        app.requirements = req.requirements

        if req.icon_path:
            app.icon_id = req.icon_id
            app.icon_path = req.icon_path
        if req.screenshots:
            app.screenshots = req.screenshots

        app.save()

        req.status = "approved"
        req.save()
        req.delete()
        self.message_user(request, "Приложение успешно обновлено!", messages.SUCCESS)
        return redirect(
            reverse("admin:marketplace_appeditrequests_change", args=[object_id])
        )

    @action(
        description="Отклонить заявку",
        icon="cancel",
        attrs={"class": "bg-error-600 text-white"},
    )
    def reject_request(self, request, object_id):
        req = self.get_object(request, object_id)
        req.status = "rejected"
        req.save()
        req.delete()
        self.message_user(request, "Заявка отклонена", messages.INFO)
        return redirect(
            reverse("admin:marketplace_appeditrequests_change", args=[object_id])
        )

    fieldsets = (
        (
            "Основная информация по заявке",
            {
                "fields": (
                    "user",
                    "category",
                    "title",
                    "slogan",
                    "description",
                    "price",
                    "icon_path",
                    "screenshots",
                    "developer_site",
                ),
                "description": "Информация, предоставленная пользователем в заявке на изменение информации в приложении",
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


@admin.register(AppReportRequests)
class AppReportRequestsAdmin(SafeDeleteAdmin):
    list_display = ("id", "app_link", "user_link", "get_reason_display", "created_at")
    list_filter = SafeDeleteAdmin.list_filter + ["id", "created_at", "reason"]
    actions_detail = ["resolve_report_detail", "dismiss_report_detail"]
    readonly_fields = (
        "user_info_link",
        "app_details_link",
        "user",
        "app",
        "reason",
        "description",
        "created_at",
    )

    @action(description="Пометить как решенное и удалить", icon="done_all")
    def resolve_report_detail(self, request, object_id):
        self._delete_report(request, object_id, "Жалоба обработана и удалена")
        return redirect(reverse("admin:marketplace_appreportrequests_changelist"))

    @action(description="Ложная жалоба (удалить)", icon="close")
    def dismiss_report_detail(self, request, object_id):
        self._delete_report(request, object_id, "Запись удалена")
        return redirect(reverse("admin:marketplace_appreportrequests_changelist"))

    def _delete_report(self, request, object_id, message):
        obj = AppReportRequests.objects.filter(id=object_id).first()
        if obj:
            obj.delete()
            self.message_user(request, message, messages.SUCCESS)

    def _set_status(self, object_id, status_value):
        AppReportRequests.objects.filter(id=object_id).update(status=status_value)

    def app_link(self, obj):
        if not obj.app:
            return "---"
        url = reverse("admin:marketplace_application_change", args=[obj.app.id])
        return format_html(
            '<a href="{}" style="font-weight:bold; color: #3b82f6;">{}</a>',
            url,
            obj.app.title,
        )

    app_link.short_description = "Приложение"

    def user_link(self, obj):
        if not obj.user:
            return "---"
        url = reverse("admin:user_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)

    user_link.short_description = "Автор"

    def user_info_link(self, obj):
        if not obj.user:
            return "Нет данных пользователя"
        url_site = f"/profile.php?id={obj.user.id}"
        return format_html(
            """
            <div style="line-height: 1.5;">
                <a href="{}" target="_blank" style="font-weight: bold; color: #3b82f6;">🔗 Профиль на сайте</a><br>
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

    def app_details_link(self, obj):
        if not obj.app:
            return "Приложение не найдено"
        icon_url = obj.app.icon_url
        admin_url = reverse("admin:marketplace_application_change", args=[obj.app.id])

        return format_html(
            """
            <div style="line-height: 1.5;">
                <img src="{}" width="40" height="40" style="border-radius:4px; margin-bottom:10px; object-fit: cover;"/><br>
                <a href="{}" style="font-weight: bold; color: #3b82f6;">Редактировать приложение</a><br>
                <span style="color: #666;">Название:</span> {}<br>
                <span style="color: #666;">Слоган:</span> {}<br>
                <span style="color: #666;">Описание:</span> {}<br>
                <span style="color: #666;">Сайт разработчика:</span> {}<br>
                <span style="color: #666;">Опубликовано:</span> {}<br>
                <span style="color: #666;">ID:</span> {}
            </div>
            """,
            icon_url,
            admin_url,
            obj.app.title,
            obj.app.slogan,
            obj.app.description,
            obj.app.developer_site,
            obj.app.published,
            obj.app.id,
        )

    app_details_link.short_description = ""

    fieldsets = (
        (
            "Статус и вердикт",
            {
                "fields": ("status",),
                "description": "Текущее состояние обработки жалобы модератором.",
            },
        ),
        (
            "Суть жалобы",
            {
                "fields": ("reason", "description", "created_at"),
                "description": "Информация, предоставленная пользователем при подаче репорта.",
            },
        ),
        (
            "Объект жалобы (Приложение)",
            {
                "fields": ("app_details_link",),
                "description": "Сведения о приложении, на которое поступила жалоба.",
            },
        ),
        (
            "Информация об авторе жалобы",
            {
                "fields": ("user_info_link",),
                "description": "Данные пользователя, отправившего этот репорт.",
            },
        ),
    )
