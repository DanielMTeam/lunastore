from django.contrib import admin
from django.core.exceptions import PermissionDenied
from safedelete.models import HARD_DELETE
from unfold.admin import ModelAdmin
from unfold.decorators import action, display


class TrashFilter(admin.SimpleListFilter):
    title = 'Состояние'
    parameter_name = 'trash'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Активные'),
            ('deleted', 'В корзине'),
            ('all', 'Все (включая корзину)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'deleted':
            return queryset.filter(deleted__isnull=False)
        elif self.value() == 'all':
            return queryset
        return queryset.filter(deleted__isnull=True)


class SafeDeleteAdmin(ModelAdmin):
    list_filter = [TrashFilter]
    actions = ['restore_objects', 'hard_delete_objects']

    def get_queryset(self, request):
        if hasattr(self.model, 'all_objects'):
            return self.model.all_objects.all()
        elif hasattr(self.model.objects, 'all_with_deleted'):
            return self.model.objects.all_with_deleted()
        return super().get_queryset(request)

    @display(description="В корзине", boolean=True)
    def is_in_trash(self, obj):
        return hasattr(obj, 'deleted') and bool(obj.deleted)

    def delete_model(self, request, obj):
        # Если объект уже помечен удаленным (в корзине) — удаляем окончательно
        if getattr(obj, 'deleted', None) is not None:
            obj.delete(force_policy=HARD_DELETE)
        else:
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        # Если массовое удаление выполняется в корзине, очищаем навсегда
        if request.GET.get('trash') == 'deleted':
            for obj in queryset:
                obj.delete(force_policy=HARD_DELETE)
        else:
            super().delete_queryset(request, queryset)

    @action(description="Восстановить выбранные из корзины", permissions=["change"])
    def restore_objects(self, request, queryset):
        if not self.has_change_permission(request):
            raise PermissionDenied
        count = 0
        for obj in queryset:
            if hasattr(obj, "undelete") and self.has_change_permission(request, obj):
                obj.undelete()
                count += 1
        self.message_user(request, f"Восстановлено объектов: {count}.")

    @action(description="Удалить навсегда (Очистить из БД)", permissions=["delete"])
    def hard_delete_objects(self, request, queryset):
        if not self.has_delete_permission(request):
            raise PermissionDenied
        count = 0
        for obj in queryset:
            if self.has_delete_permission(request, obj):
                obj.delete(force_policy=HARD_DELETE)
                count += 1
        self.message_user(request, f"Окончательно удалено из БД объектов: {count}.")
