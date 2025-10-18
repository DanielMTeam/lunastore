from django.shortcuts import render, redirect
from django.http import HttpResponse

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
    query = request.GET.get('q')  # get the value associated with 'q'
    id = request.GET.get('id')
    print(f'{id}, type: {type(id)}')
    context = {
        'app_id': id
    }
    return render(request, 'storepage.html', context)