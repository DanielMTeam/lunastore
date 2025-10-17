from django.shortcuts import render
from django.http import HttpResponse

# views of home page 

def marketplace(request):
    return HttpResponse("hello world!!!")