from django.urls import path
from . import views

app_name = "guide_page"

urlpatterns = [
    path('introduction/', views.introduction_view, name='introduction'),
    path('help/', views.help_view, name='help'),

]