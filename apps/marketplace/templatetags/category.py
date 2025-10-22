from django import template
from apps.marketplace.models import Category

# register inclusion tag
register = template.Library()

@register.inclusion_tag('includes/categories.html')
def show_categories(active_category=None):
    categories = Category.objects.all()
    print(categories)
    return {'categories': categories, 'active_category': active_category}