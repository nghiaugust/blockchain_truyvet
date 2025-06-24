from django.shortcuts import render

def introduction_view(request):
    return render(request, 'guide_page/introduction.html')

def help_view(request):
    return render(request, 'guide_page/help.html')
