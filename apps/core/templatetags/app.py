from django import template
from apps.marketplace.models import Application, Distribution

# register inclusion tag
register = template.Library()

# some utils
# check if app is demo status
def is_demo(app_id):
    try:
        app = Application.objects.get(id=app_id)
        return app.is_demo
    except Application.DoesNotExist:
        return False

# check if app is under dmca
def is_dmca(app_id):
    try:
        app = Application.objects.get(id=app_id)
        return app.is_under_dmca
    except Application.DoesNotExist:
        return False
    
def price_value(app_id):
    try:
        app = Application.objects.get(id=app_id)
        return app.price
    except Application.DoesNotExist:
        return 0

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

@register.inclusion_tag('includes/demo_flag.html')
def demo_visible(app_id):
    app = None
    demo = False
    try:
        demo = is_demo(app_id)
    except Application.DoesNotExist:
        app = None
        demo = None
    return {'app': app, 'app_id': app_id, 'is_demo': bool(demo)}

@register.inclusion_tag('includes/dmca_flag.html')
def dmca_visible(app_id):
    app = None
    dmca = False
    try:
        dmca = is_dmca(app_id)
    except Application.DoesNotExist:
        app = None
        dmca = None
    return {'app': app, 'app_id': app_id, 'is_dmca': bool(dmca)}

@register.inclusion_tag('includes/install_app_box.html')
def install_app_box(app_id):
    app = None
    dmca = False
    try:
        dmca = is_dmca(app_id)
    except Application.DoesNotExist:
        app = None
        dmca = None
    return {'app': app, 'app_id': app_id, 'is_dmca': bool(dmca)}

@register.inclusion_tag('includes/install_app_button.html')
def install_app_button(app_id):
    app = None
    dmca = False
    demo = False
    try:
        app = Application.objects.get(id=app_id)
        dmca = is_dmca(app_id)
        demo = is_demo(app_id)
    except Application.DoesNotExist:
        app = None
        dmca = None
        demo = None
        price = 0
    return {'app': app, 'app_id': app_id, 'is_dmca': bool(dmca), 'is_demo': bool(demo)}