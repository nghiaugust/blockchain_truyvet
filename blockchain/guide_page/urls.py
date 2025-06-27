from django.urls import path
from . import views

app_name = "guide_page"

urlpatterns = [
    path('main/', views.main_view, name='main'),
    path('help/', views.help_view, name='help'),

]