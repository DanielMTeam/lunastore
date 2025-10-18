from django.contrib import admin
from .models import *


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass



@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    pass

@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    pass
