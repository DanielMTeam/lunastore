from django import template
from apps.marketplace.models import Category

# register inclusion tag
register = template.Library()

@register.inclusion_tag('includes/categories.html')
def showCategories():
    categories = Category.objects.all()
    print(categories)
    return {'categories': categories}