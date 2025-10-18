from django import template
from apps.marketplace.models import Application, Distribution

# register inclusion tag
register = template.Library()

@register.inclusion_tag('includes/application.html')
def show_app(app_id):
    app = None
    screenshots = []
    download_url = None
    try:
        app = Application.objects.get(id=app_id)
        screenshots = app.screenshots
        distribution = Distribution.objects.filter(app=app).first()
        if distribution and hasattr(distribution, 'url') and distribution.url:
             download_url = distribution.url.url
    except Application.DoesNotExist:
        app = None
        screenshots = []
        download_url = None

    return {'app': app, 'screenshots': screenshots, 'download_url': download_url, 'app_id': app_id}