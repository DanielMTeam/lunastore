from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import action, display

class TrashFilter(admin.SimpleListFilter):
    title = 'Состояние'
    parameter_name = 'trash'

    def lookups(self, request, model_admin):
        return (('active', 'Активные'), ('deleted', 'В корзине'))

    def queryset(self, request, queryset):
        if self.value() == 'deleted':
            return queryset.model.objects.deleted_only()
        return queryset.model.objects.filter(deleted__isnull=True)

class SafeDeleteAdmin(ModelAdmin):
    list_filter = [TrashFilter]
    actions = ['restore_objects', 'hard_delete_objects']

    def get_queryset(self, request):
        if hasattr(self.model.objects, 'all_with_deleted'):
            return self.model.objects.all_with_deleted()
        return super().get_queryset(request)

    @display(description="В корзине", boolean=True)
    def is_in_trash(self, obj):
        return hasattr(obj, 'deleted') and bool(obj.deleted)

    @action(description="Восстановить выбранные")
    def restore_objects(self, request, queryset):
        for obj in queryset:
            obj.undelete()
        self.message_user(request, "Объекты восстановлены.")

    @action(description="Удалить навсегда (Очистить)")
    def hard_delete_objects(self, request, queryset):
        for obj in queryset:
            obj.delete(force_policy=2) 
        self.message_user(request, "Объекты окончательно удалены из БД.")