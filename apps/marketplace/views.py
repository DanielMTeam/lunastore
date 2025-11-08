from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from .models import Application, Distribution, Category
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator


# views of home page 

# redirect to home (index.php) page from (/) page
def home_redirect(request):
    
    return redirect('/index.php')

# home page
def marketplace(request):
    return render(request, 'index.html')

def category(request):
    id = request.GET.get('id')
    page = request.GET.get('page')

    # get model objects
    obj_category = get_object_or_404(Category, id=id)
    obj_apps = Application.objects.filter(category__name=obj_category.name).order_by('-published')
    
    # paginator logic
    paginator = Paginator(obj_apps,10)
    page_obj=paginator.get_page(page)
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=2, on_ends=1)
    
    context = {
        'page_obj': page_obj,
        'page_range': page_range, 
        'active_category': obj_category,
        'name': obj_category.name,
        'description': obj_category.description,
        'count': obj_apps.count
    }
    return render(request, 'category.html', context)

def app(request):
    id = request.GET.get('id')

    obj = get_object_or_404(Application, id=id)
    obj_dist = Distribution.objects.filter(app__id=id).order_by('-published').first()
    
    context = {
        'app_id': obj.id,
        'is_demo': obj.is_demo,
        'is_under_dmca': obj.is_under_dmca,
        'price': obj.price,
        'developer_site': obj.developer_site,
        'download_url': obj_dist.url if obj_dist else None,
        'icon_url': obj.icon.url,
        'title': obj.title,
        'slogan': obj.slogan,
        'description': obj.description,
        'screenshots': obj.screenshots
    }
    return render(request, 'storepage.html', context)