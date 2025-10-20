from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Application, Distribution

# views of home page 

# redirect to home (index.php) page from (/) page
def home_redirect(request):
    return redirect('/index.php')

# home page
def marketplace(request):
    return render(request, 'index.html')

def category(request):
    pass

def app(request):
    id = request.GET.get('id')
    # print for debug only
    print(f'{id}, type: {type(id)}')
    obj = Application.objects.get(id=id)
    obj_dist = Distribution.objects.filter(app__id=id).order_by('-published').first()
    context = {
        'app_id': obj.id,
        'is_demo': obj.is_demo,
        'is_under_dmca': obj.is_under_dmca,
        'price': obj.price,
        'developer_site': obj.developer_site,
        'download_url': obj_dist.url,
        'icon_url': obj.icon.url,
        'title': obj.title,
        'slogan': obj.slogan,
        'description': obj.description,
        'screenshots': obj.screenshots
    }
    print(context)
    return render(request, 'storepage.html', context)