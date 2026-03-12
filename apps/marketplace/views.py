from django.shortcuts import render, redirect, get_object_or_404
from .models import Application, Distribution, Category
from django.core.paginator import Paginator
from apps.user.decorators import developer_required
from .forms import AppCreateForm, AppEditForm, AppReportForm, DistributionForm
from django.contrib.auth.decorators import login_required
from .decorators import user_is_owner
from django.contrib.postgres.search import TrigramSimilarity
from django.contrib import messages
from django.utils.translation import gettext as _
from django.urls import reverse
from django.core.exceptions import PermissionDenied


def _format_legacy_date(value):
    return value.strftime('%d.%m.%Y %H:%M') if value else ''


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
    download_page_url = f'{reverse("download_list")}?id={obj.id}'
    
    context = {
        'app_id': obj.id,
        'is_demo': obj.is_demo,
        'is_dmca': obj.is_under_dmca,
        'is_under_dmca': obj.is_under_dmca,
        'price': obj.price,
        'developer_site': obj.developer_site,
        'download_page_url': download_page_url,
        'latest_distribution': obj_dist,
        'icon_url': obj.icon.url if obj.icon else '',
        'title': obj.title,
        'slogan': obj.slogan,
        'description': obj.description,
        'screenshots': obj.screenshots
    }
    return render(request, 'storepage.html', context)


def download_list(request):
    app_id = request.GET.get('id')
    if not app_id:
        return redirect('home')

    app_obj = get_object_or_404(Application, id=app_id)
    distributions = list(Distribution.objects.filter(app=app_obj))
    sort_field = request.GET.get('sort', 'version')
    order = request.GET.get('order', 'asc')

    def sort_key(dist):
        if sort_field == 'published':
            return dist.published or dist.pk
        return dist.version or ''

    is_desc = order == 'desc'
    distributions.sort(key=sort_key, reverse=is_desc)

    sort_links = {}
    for field in ('version', 'published'):
        next_order = 'desc' if sort_field == field and order == 'asc' else 'asc'
        sort_links[field] = f'{reverse("download_list")}?id={app_obj.id}&sort={field}&order={next_order}'
    latest_dist = distributions[0] if distributions else None
    latest_id = latest_dist.id if latest_dist else None

    dist_rows = []
    for dist in distributions:
        link = dist.file.url if dist.file else dist.url
        dist_rows.append({
            'id': dist.id,
            'version': dist.version,
            'changelog': dist.changelog,
            'published': _format_legacy_date(dist.published),
            'is_latest': dist.id == latest_id,
            'link': link or '#',
            'has_download': bool(link),
        })

    context = {
        'app': app_obj,
        'icon_url': app_obj.icon.url if app_obj.icon else '',
        'slogan': app_obj.slogan,
        'description': app_obj.description,
        'developer_site': app_obj.developer_site,
        'distributions': dist_rows,
        'manage_url': f'{reverse("manage_distributions")}?id={app_obj.id}',
        'current_sort': sort_field,
        'current_order': order,
        'sort_links': sort_links,
        'owner_can_manage': request.user.is_authenticated and request.user == app_obj.user,
        'ad_link': 'https://store.myslivets.com',
        'app_link': f'/app.php?id={app_obj.id}',
    }

    return render(request, 'download_list.html', context)

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
def manage_distributions(request):
    app_id = request.GET.get('id')
    app_obj = get_object_or_404(Application, id=app_id)

    if app_obj.user != request.user:
        raise PermissionDenied("ERROR_YOURE_NOT_OWNER_OF_APP")

    distributions = Distribution.objects.filter(app=app_obj).order_by('-published')
    form = DistributionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        distribution = form.save(commit=False)
        distribution.app = app_obj
        distribution.save()
        messages.success(request, _("Новая дистрибуция создана"))
        return redirect(reverse("manage_distributions") + "?id=" + str(app_obj.id))

    dist_rows = []
    for dist in distributions:
        dist_rows.append({
            'id': dist.id,
            'version': dist.version,
            'published': _format_legacy_date(dist.published),
            'changelog': dist.changelog,
            'edit_url': reverse('distribution_edit', kwargs={'dist_pk': dist.pk}),
            'delete_url': reverse('distribution_delete', kwargs={'dist_pk': dist.pk}),
        })

    context = {
        'app': app_obj,
        'form': form,
        'distributions': dist_rows,
        'download_list_url': reverse('download_list') + "?id=" + str(app_obj.id),
    }
    return render(request, 'manage_distributions.html', context)

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


@login_required
def distribution_edit(request, dist_pk):
    distribution = get_object_or_404(Distribution, pk=dist_pk)
    if distribution.app.user != request.user:
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    form = DistributionForm(request.POST or None, request.FILES or None, instance=distribution)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _("Изменения дистрибуции сохранены"))
        return redirect(reverse('manage_distributions') + '?id=' + str(distribution.app.id))

    context = {
        'form': form,
        'app': distribution.app,
        'distribution': distribution,
        'download_list_url': reverse('download_list') + '?id=' + str(distribution.app.id),
    }
    return render(request, 'distribution_form.html', context)


@login_required
def distribution_delete(request, dist_pk):
    distribution = get_object_or_404(Distribution, pk=dist_pk)
    if distribution.app.user != request.user:
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))

    if request.method == 'POST':
        distribution.delete()
        messages.success(request, _("Дистрибуция удалена"))
    else:
        messages.warning(request, _("Нужно подтвердить удаление через POST"))

    return redirect(reverse('manage_distributions') + '?id=' + str(distribution.app.id))

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

@login_required
def report_app(request):
    id = request.GET.get('id')
    obj = get_object_or_404(Application, id=id)
    
    if request.method == 'POST':
        form = AppReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.app = obj
            report.save()
            messages.success(request, _("PAGE_REPORTAPP_SUCCESS_MSG"))
            return redirect('home')
    else:
        form = AppReportForm()    
    context = {
        'form': form,
        'name': obj.title,
        'slogan': obj.slogan,
        'icon': obj.icon.url,
    }
    return render(request, 'report_app.html', context)
