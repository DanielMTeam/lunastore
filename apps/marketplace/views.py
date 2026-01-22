from django.shortcuts import render, redirect
from .models import Application, Distribution, Category
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from apps.user.decorators import developer_required
from .forms import AppCreateForm, AppEditForm
from django.contrib.auth.decorators import login_required
from .decorators import user_is_owner
from django.contrib.postgres.search import TrigramSimilarity


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
    paginator = Paginator(obj_apps, 10)
    page_obj = paginator.get_page(page)
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

def faq(request):
    return render(request, 'faq.html')

@developer_required
def app_add(request):
    if request.method == 'POST':
        form = AppCreateForm(request.POST, request.FILES)
        if form.is_valid():
            app_request = form.save(commit=False)
            app_request.user = request.user
            app_request.save()
            return redirect('home')
        else:
            print("Form Errors:", form.errors)
    else:
        form = AppCreateForm()
    return render(request, 'app_add.html', {'form':form})

@login_required
def settings_apps(request):
    managed_apps = Application.objects.filter(user=request.user)
    return render(request, 'settings_apps.html', {'managed_apps':managed_apps})

@login_required
@user_is_owner(Application)
def application_edit_info(request, pk):
    obj = get_object_or_404(Application,pk=pk)
    
    if request.method == 'POST':
        form = AppEditForm(target_app=obj, data=request.POST, files=request.FILES)
        if form.is_valid():
            edit_request = form.save(commit=False)
            edit_request.user = request.user
            edit_request.save()
            return redirect('edit_app_info', pk=obj.pk)
    else:
        form = AppEditForm(target_app=obj)
    return render(request, 'admin_app.html', {'obj':obj,'form':form})

def search(request):
    query = request.GET.get('q')
    view_mode = request.GET.get('view', 'tiles')
    
    results = []
    
    if query:
        results = Application.objects.annotate(similarity=TrigramSimilarity('title', query) + TrigramSimilarity('description', query) + TrigramSimilarity('slogan', query),).filter(similarity__gt=0.1).order_by('-similarity')
    else:
        results = Application.objects.none()
        
    paginator = Paginator(results, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'results': page_obj,  
        'query': query,       
        'view_mode': view_mode
    }
    return render(request, 'search.html', context)