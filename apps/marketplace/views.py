from django.shortcuts import render, redirect
from django.http import HttpResponse

# views of home page 

# redirect to home (index.php) page from (/) page
def homeRedirect(request):
    return redirect('/index.php')

# home page
def marketplace(request):
    return render(request, 'index.html')