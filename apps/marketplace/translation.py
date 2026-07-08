from modeltranslation.translator import register, TranslationOptions
from .models import Application, Category, AppCreateRequests, Distribution, AppEditRequests, DistributionEditRequests, DistributionCreateRequests, Badge

@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name', 'description')

@register(Badge)
class BadgeTranslationOptions(TranslationOptions):
    fields = ('name',)

@register(Application)
class ApplicationTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'requirements', 'slogan')

@register(AppCreateRequests)
class AppCreateRequestsTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'requirements', 'slogan')

@register(Distribution)
class DistributionTranslationOptions(TranslationOptions):
    fields = ('changelog',)

@register(AppEditRequests)
class AppEditRequestsTranslationOptions(TranslationOptions):
    fields = ('title', 'description', 'requirements', 'slogan')

@register(DistributionCreateRequests)
class DistributionRequestTranslationOptions(TranslationOptions):
    fields = ('changelog',)

@register(DistributionEditRequests)
class DistributionEditRequestTranslationOptions(TranslationOptions):
    fields = ('changelog',)
