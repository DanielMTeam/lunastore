from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold import admin as unfold_admin
from unfold.decorators import action
from apps.core.tasks import send_notification
from safedelete.models import HARD_DELETE
from lunastore.mixins import SafeDeleteAdmin
from . import translation
from .forms import ApplicationAdminForm
from .models import *
from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline


class DistributionInline(TranslationTabularInline):
    model = Distribution
    fields = ("version", "url", "changelog", "published")
    readonly_fields = ("published",)
    extra = 0


@admin.register(Distribution)
class DistributionAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):
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

@admin.register(DistributionCreateRequests)
class DistributionCreateAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):
    change_list_template = "admin/decline_forms/change_list_custom.html"
    change_form_template = "admin/decline_forms/change_form_custom.html"

    list_display = ("id", "app", "version", "user", "status", "created_at")
    search_fields = ["app__title", "version", "user__username"]
    list_filter = SafeDeleteAdmin.list_filter + ["status", "created_at"]
    actions_detail = ["approve_request", "reject_request"]
    actions = ["approve_request", "reject_request"]

    readonly_fields = ("app", "user", "status", "version", "cdn_file_id", "url", "changelog", "security_check")

    fieldsets = (
        ("Информация о дистрибуции", {
            "fields": ("app", "version", "changelog", "url", "cdn_file_id")
        }),
        ("Безопасность", {
            "fields": ("security_check",),
            "description": "Сверка хэша от CDN (LunaSpire) с результатами VirusTotal. Если ссылка и хэш не указаны, проверка не выполняется."
        }),
        ("Статус и автор", {
            "fields": ("user", "status")
        }),
    )

    @admin.display(description="Проверка хэша")
    def security_check(self, obj):
        if not obj.cdn_hash:
            return mark_safe('<span class="text-gray-500 font-medium">Файл не загружался (только внешняя ссылка).</span>')

        # form link to VirusTotal report
        vt_link = format_html(
            '<a href="{}" target="_blank" class="font-semibold text-blue-600 hover:text-blue-800 underline">Перейти к отчету VirusTotal</a> ({})',
            obj.virustotal_url, obj.virustotal_url
        ) if obj.virustotal_url else '<span class="text-red-600 font-bold">Ссылка не указана!</span>'

        # unique IDs for HTML elements (in case there are multiple blocks on the page)
        input_id = f"vt_input_{obj.id}"
        result_id = f"vt_result_{obj.id}"

        html = f"""
        <div class="p-4 bg-gray-50 rounded-md border border-gray-200">
            <div class="mb-3">
                <span class="text-gray-600 text-sm">Хэш на CDN (LunaSpire):</span><br>
                <code class="bg-white px-2 py-1 border border-gray-200 rounded text-sm text-gray-800 mt-1 inline-block">{obj.cdn_hash}</code>
            </div>

            <div class="mb-4">
                {vt_link}
            </div>

            <div class="mt-4 p-4 border border-gray-200 bg-white rounded-md shadow-sm">
                <label class="block text-sm font-medium text-gray-700 mb-2">Вставьте хэш с VirusTotal для сверки:</label>
                <div class="flex items-center gap-2">
                    <input type="text" id="{input_id}"
                           class="border border-gray-300 rounded px-3 py-2 w-full max-w-lg text-sm focus:ring-primary-600 focus:border-primary-600 outline-none"
                           placeholder="Вставьте хэш сюда...">

                    <button type="button" onclick="compareHashes_{obj.id}()"
                            class="bg-primary-600 hover:bg-primary-700 text-white font-medium py-2 px-4 rounded text-sm transition-colors cursor-pointer">
                        Сверить
                    </button>
                </div>
                <div id="{result_id}" class="mt-3 text-sm h-5"></div>
            </div>

            <script>
                function compareHashes_{obj.id}() {{
                    const cdnHash = "{obj.cdn_hash}".toLowerCase().trim();

                    const inputElem = document.getElementById("{input_id}");
                    const resultElem = document.getElementById("{result_id}");
                    const vtHash = inputElem.value.toLowerCase().trim();

                    if (!vtHash) {{
                        resultElem.innerHTML = "<span class='text-gray-500'>Пожалуйста, вставьте хэш в поле.</span>";
                        return;
                    }}

                    if (vtHash === cdnHash) {{
                        resultElem.innerHTML = "<span class='text-green-600 font-bold'>Хэши совпадают! Файл подлинный.</span>";
                    }} else {{
                        resultElem.innerHTML = "<span class='text-red-600 font-bold'>Хэши не совпадают! Это другой файл.</span>";
                    }}
                }}
            </script>
        </div>
        """

        return mark_safe(html)

    @action(description="Одобрить заявку", icon="check_circle", attrs={"class": "bg-success-600 text-white"})
    def approve_request(self, request, object_id):
        req = self.get_object(request, object_id)
        if req.status == "approved":
            self.message_user(request, "Уже одобрено", messages.WARNING)
            return redirect(reverse("admin:marketplace_distributioncreaterequests_changelist"))

        dist = Distribution(
            app=req.app,
            version=req.version,
            cdn_file_id=req.cdn_file_id,
            url=req.url,
        )

        for lang_code, _ in settings.LANGUAGES:
            lang_field = f"changelog_{lang_code}"
            val = getattr(req, lang_field, None)
            setattr(dist, lang_field, val)

        dist.save()

        req.status = "approved"
        req.save()

        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_DISTREQ_ACCEPTED_TITLE",
            content_key="NOTIF_DISTREQ_ACCEPTED_DESCRIPTION",
            context={"app_name": req.app.title, "version": req.version},
            meta={"icon": "help.png"}
        )

        req.delete(force_policy=HARD_DELETE)
        self.message_user(request, "Дистрибуция успешно создана и опубликована!", messages.SUCCESS)
        return redirect(reverse("admin:marketplace_distributioncreaterequests_changelist"))

    @action(description="Отклонить заявку", icon="cancel", attrs={"class": "bg-error-600 text-white"})
    def reject_request(self, request, object_id):
        req = self.get_object(request, object_id)
        reason = request.POST.get("reject_reason", "Нарушение правил площадки")
        req.status = "rejected"
        req.save()

        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_DISTREQ_DECLINED_TITLE",
            content_key="NOTIF_DISTREQ_DECLINED_DESCRIPTION",
            context={"app_name": req.app.title, "version": req.version, "reason": reason},
            meta={"icon": "help.png"}
        )
        req.delete(force_policy=HARD_DELETE)
        self.message_user(request, "Заявка на дистрибуцию отклонена", messages.INFO)
        return redirect(reverse("admin:marketplace_distributioncreaterequests_changelist"))

@admin.register(DistributionEditRequests)
class DistributionEditRequestAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):
    change_list_template = "admin/decline_forms/change_list_custom.html"
    change_form_template = "admin/decline_forms/change_form_custom.html"

    list_display = ("id", "target_distribution", "user", "status", "created_at")
    search_fields = ("target_distribution__app__title", "version", "user__username")
    list_filter = SafeDeleteAdmin.list_filter + ["status", "created_at"]
    actions_detail = ["approve_request", "reject_request"]
    actions = ["approve_request", "reject_request"]

    readonly_fields = ("app", "target_distribution", "user", "status", "version", "cdn_file_id", "url", "changelog", "security_check")

    fieldsets = (
        ("Информация об изменениях", {
            "fields": ("target_distribution", "version", "changelog", "url", "cdn_file_id")
        }),
        ("Безопасность", {
            "fields": ("security_check",),
            "description": "Сверка хэша от CDN (LunaSpire) с результатами VirusTotal. Если ссылка и хэш не указаны, проверка не выполняется."
        }),
        ("Статус и автор", {
            "fields": ("user", "status")
        }),
    )

    @admin.display(description="Проверка хэша")
    def security_check(self, obj):
        if not obj.cdn_hash:
            return mark_safe('<span class="text-gray-500 font-medium">Файл не загружался (только внешняя ссылка).</span>')

        # form link to VirusTotal report
        vt_link = format_html(
            '<a href="{}" target="_blank" class="font-semibold text-blue-600 hover:text-blue-800 underline">Перейти к отчету VirusTotal</a> ({})',
            obj.virustotal_url, obj.virustotal_url
        ) if obj.virustotal_url else '<span class="text-red-600 font-bold">Ссылка не указана!</span>'

        # unique IDs for HTML elements (in case there are multiple blocks on the page)
        input_id = f"vt_input_{obj.id}"
        result_id = f"vt_result_{obj.id}"

        html = f"""
        <div class="p-4 bg-gray-50 rounded-md border border-gray-200">
            <div class="mb-3">
                <span class="text-gray-600 text-sm">Хэш на CDN (LunaSpire):</span><br>
                <code class="bg-white px-2 py-1 border border-gray-200 rounded text-sm text-gray-800 mt-1 inline-block">{obj.cdn_hash}</code>
            </div>

            <div class="mb-4">
                {vt_link}
            </div>

            <div class="mt-4 p-4 border border-gray-200 bg-white rounded-md shadow-sm">
                <label class="block text-sm font-medium text-gray-700 mb-2">Вставьте хэш с VirusTotal для сверки:</label>
                <div class="flex items-center gap-2">
                    <input type="text" id="{input_id}"
                           class="border border-gray-300 rounded px-3 py-2 w-full max-w-lg text-sm focus:ring-primary-600 focus:border-primary-600 outline-none"
                           placeholder="Вставьте хэш сюда...">

                    <button type="button" onclick="compareHashes_{obj.id}()"
                            class="bg-primary-600 hover:bg-primary-700 text-white font-medium py-2 px-4 rounded text-sm transition-colors cursor-pointer">
                        Сверить
                    </button>
                </div>
                <div id="{result_id}" class="mt-3 text-sm h-5"></div>
            </div>

            <script>
                function compareHashes_{obj.id}() {{
                    const cdnHash = "{obj.cdn_hash}".toLowerCase().trim();

                    const inputElem = document.getElementById("{input_id}");
                    const resultElem = document.getElementById("{result_id}");
                    const vtHash = inputElem.value.toLowerCase().trim();

                    if (!vtHash) {{
                        resultElem.innerHTML = "<span class='text-gray-500'>Пожалуйста, вставьте хэш в поле.</span>";
                        return;
                    }}

                    if (vtHash === cdnHash) {{
                        resultElem.innerHTML = "<span class='text-green-600 font-bold'>Хэши совпадают! Файл подлинный.</span>";
                    }} else {{
                        resultElem.innerHTML = "<span class='text-red-600 font-bold'>Хэши не совпадают! Это другой файл.</span>";
                    }}
                }}
            </script>
        </div>
        """

        return mark_safe(html)

    @action(description="Одобрить изменения", icon="check_circle", attrs={"class": "bg-success-600 text-white"})
    def approve_request(self, request, object_id):
        req = self.get_object(request, object_id)
        if req.status == "approved":
            self.message_user(request, "Уже одобрено", messages.WARNING)
            return redirect(reverse("admin:marketplace_distributioneditrequests_changelist"))

        dist = req.target_distribution
        dist.version = req.version
        dist.url = req.url

        if req.cdn_file_id:
            dist.cdn_file_id = req.cdn_file_id

        for lang_code, _ in settings.LANGUAGES:
            lang_field = f"changelog_{lang_code}"
            if hasattr(req, lang_field):
                setattr(dist, lang_field, getattr(req, lang_field))

        dist.save()

        req.status = "approved"
        req.save()

        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_DISTEDITREQ_ACCEPTED_TITLE",
            content_key="NOTIF_DISTEDITREQ_ACCEPTED_DESCRIPTION",
            context={"app_name": req.app.title, "version": req.version},
            meta={"icon": "help.png"}
        )
        req.delete(force_policy=HARD_DELETE)
        self.message_user(request, "Изменения успешно применены к дистрибуции!", messages.SUCCESS)
        return redirect(reverse("admin:marketplace_distributioneditrequests_changelist"))

    @action(description="Отклонить изменения", icon="cancel", attrs={"class": "bg-error-600 text-white"})
    def reject_request(self, request, object_id):
        req = self.get_object(request, object_id)
        reason = request.POST.get("reject_reason", "Нарушение правил площадки")
        req.status = "rejected"
        req.save()

        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_DISTEDITREQ_DECLINED_TITLE",
            content_key="NOTIF_DISTEDITREQ_DECLINED_DESCRIPTION",
            context={"app_name": req.app.title, "version": req.version, "reason": reason},
            meta={"icon": "help.png"}
        )
        req.delete(force_policy=HARD_DELETE)
        self.message_user(request, "Правки отклонены", messages.INFO)
        return redirect(reverse("admin:marketplace_distributioneditrequests_changelist"))


@admin.register(Category)
class CategoryAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):
    pass


@admin.register(Application)
class ApplicationAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):


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
                    "original_author",
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
class AppCreateRequestsAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):
    change_list_template = "admin/decline_forms/change_list_custom.html"
    change_form_template = "admin/decline_forms/change_form_custom.html"

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
        "original_author",
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

        app = Application(
            user=req.user,
            category=req.category,
            price=req.price,
            icon_id=req.icon_id,
            icon_path=req.icon_path,
            screenshots=req.screenshots,
            developer_site=req.developer_site,
            original_author=req.original_author,
        )

        # copy locale
        trans_fields = ["title", "description", "requirements", "slogan"]
        for field in trans_fields:
            for lang_code, _ in settings.LANGUAGES:
                lang_field = f"{field}_{lang_code}"
                val = getattr(req, lang_field, None)
                setattr(app, lang_field, val)

        app.save()
        req.status = "approved"
        req.save()
        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_APPREQ_ACCEPTED_TITLE",
            content_key="NOTIF_APPREQ_ACCEPTED_DESCRIPTION",
            context={"app_name": app.title},
            meta={"icon": "help.png"}
        )
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
        reason = request.POST.get("reject_reason")
        req.status = "rejected"
        req.save()
        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_APPREQ_DECLINED_TITLE",
            content_key="NOTIF_APPREQ_DECLINED_DESCRIPTION",
            context={"app_name": req.title, "reason": reason},
            meta={"icon": "help.png"}
        )
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
class AppEditRequestsAdmin(SafeDeleteAdmin, TabbedTranslationAdmin):
    change_list_template = "admin/decline_forms/change_list_custom.html"
    change_form_template = "admin/decline_forms/change_form_custom.html"

    list_display = ("id", "title", "user", "status")
    search_fields = ["title", "id"]
    tabs = [
        ("info_tab", "Основная информация"),
        ("user_tab", "Автор и статус"),
    ]
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
        "original_author",
        "description",
        "requirements",
        "slogan",
        "icon_preview",
        "price",
        "screenshots",
        "developer_site",
    )
    fieldsets = (
        (
            "info_tab",
            {
                "fields": (
                    "category",
                    "title",
                    "slogan",
                    "description",
                    "requirements",
                    "original_author",
                    "price",
                    "developer_site",
                    "icon_preview",
                    "screenshots",
                ),
            },
        ),
        (
            "user_tab",
            {
                "fields": (
                    "status",
                    "user",
                    "user_info_link",
                ),
            },
        ),
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
        app.original_author = req.original_author
        app.price = req.price
        app.developer_site = req.developer_site

        if req.icon_path:
            app.icon_id = req.icon_id
            app.icon_path = req.icon_path
        if req.screenshots:
            app.screenshots = req.screenshots

        trans_fields = ["title", "description", "requirements", "slogan"]
        for field in trans_fields:
            for lang_code, _ in settings.LANGUAGES:
                lang_field = f"{field}_{lang_code}"

                val = getattr(req, lang_field, None)
                setattr(app, lang_field, val)

        app.save()

        req.status = "approved"
        req.save()
        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_APPEDITREQ_ACCEPTED_TITLE",
            content_key="NOTIF_APPEDITREQ_ACCEPTED_DESCRIPTION",
            context={"app_name": req.title},
            meta={"icon": "help.png"}
        )
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
        reason = request.POST.get("reject_reason")
        req.save()
        send_notification.enqueue(
            user_id=req.user.id,
            title_key="NOTIF_APPEDITREQ_DECLINED_TITLE",
            content_key="NOTIF_APPEDITREQ_DECLINED_DESCRIPTION",
            context={"app_name": req.title, "reason": reason},
            meta={"icon": "help.png"}
        )
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
                    "original_author",
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
            obj.delete(force_policy=HARD_DELETE)
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
