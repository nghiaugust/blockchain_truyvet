from django.shortcuts import render

def main_view(request):
    return render(request, 'guide_page/main.html')

def help_view(request):
    return render(request, 'guide_page/help.html')
